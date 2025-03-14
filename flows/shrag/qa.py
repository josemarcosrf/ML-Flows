from typing import Any

from llama_index.core import get_response_synthesizer, VectorStoreIndex
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.vector_stores import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from loguru import logger
from prefect import task
from prefect.runtime import task_run
from pydantic import BaseModel
from tqdm.rich import tqdm

from flows.settings import settings
from flows.shrag.playbook import get_question_prompt, QuestionItem
from flows.shrag.schemas.answers import BaseAnswer, SummaryAnswer, YesNoEnum
from flows.shrag.schemas.questions import QuestionType


def generate_ask_run_name():
    task_name = task_run.task_name
    parameters = task_run.parameters
    # Get the QuestionItem from the kwargs
    if q := parameters.get("q"):
        if hasattr(q, "key") and q.key:
            return f"{task_name}:{q.key}"
    if q := parameters.get("questions"):
        if isinstance(q, list) and len(q) > 0:
            return f"{task_name}:{q[0].key}"

    return task_name


class QAResponse(BaseModel):
    question: str
    question_type: str
    answer: BaseAnswer


class QAgent:
    """A Question-Answering Agent implementing the RAG pipeline"""

    def __init__(self, index: VectorStoreIndex, llm: Any, reranker: Any = None):
        """Initialize the Question Agent with the index and LLM"""
        logger.info(f"🧠 Initializing QAgent with llm={llm.model}")
        self.index = index
        self.llm = llm
        self.reranker = reranker  # Optional Reranker to re-rank the retrieved nodes

    def rag(
        self,
        query: str,
        meta_filters: dict[str, Any] = {},
        output_cls: BaseModel = SummaryAnswer,
        similarity_top_k: int = settings.SIMILARITY_TOP_K,
        similarity_cutoff: float = settings.SIMILARITY_CUTOFF,
    ) -> BaseAnswer:
        """This is the in-effecct RAG pipeline. Retrieves, re-ranks, generates and formats
        the answer

        Args:
            query (str): Question to ask the RAG system
            output_cls (BaseModel, optional): Output Schema. Defaults to ExtractiveAnswer.
            meta_filters (dict[str, Any], optional): Metadata filters for retrieval. Defaults to {}.
            similarity_top_k (int, optional): Number of top results to retrieve. Defaults to 3.
            similarity_cutoff (float, optional): Similarity cutoff for retrieval. Defaults to 0.5.
        Raises:
            ValueError: If the output_cls is not a valid BaseModel
            ValueError: If the similarity_top_k is not a positive integer
            ValueError: If the similarity_cutoff is not a float between 0 and 1
        Returns:
            BaseAnswer: Retrieval Augmented Generated Answer
        """
        # Build the Retriever with its metadata filters
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key=k,
                    operator=FilterOperator.EQ,
                    value=v,
                )
                for k, v in meta_filters.items()
            ]
        )
        retriever = self.index.as_retriever(
            filters=filters,
            similarity_cutoff=similarity_cutoff,
            similarity_top_k=similarity_top_k,
        )
        # Structure the LLM as per the passed output class
        sllm = self.llm.as_structured_llm(output_cls=output_cls)

        # Configure response synthesizer. Also possible: `compact`, `refine`
        response_synthesizer = get_response_synthesizer(
            structured_answer_filtering=False, response_mode="tree_summarize", llm=sllm
        )
        # Assemble the query engine
        postprocessors = [self.reranker] if self.reranker else []
        query_engine = RetrieverQueryEngine(
            retriever=retriever,
            node_postprocessors=postprocessors,
            response_synthesizer=response_synthesizer,
        )
        # Run the Retrieval, Re-ranking and Generation of the structured response
        response = query_engine.query(query)

        return response.response

    @task(task_run_name=generate_ask_run_name)
    def ask(
        self,
        q: QuestionItem,
        meta_filters: dict[str, Any] = {},
        **kwargs,
    ) -> BaseAnswer | None:
        """Shorthand method for RAG given a 'Question Item'

        Accepts all the keyword arguments of 'rag':
        - similarity_top_k
        - similarity_cutoff

        Args:
            q (QuestionItem): The Question Collection Item to query
            meta_filters (dict[str, Any]): Metadata Retrieval filter dictionary in the form
                metadata-key, value pairs
        """
        prompt = get_question_prompt(q)
        try:
            return self.rag(
                query=prompt,
                output_cls=q.answer_schema,
                meta_filters=meta_filters,
                **kwargs,
            )
        except Exception as e:
            print(f"❌ Error extracting '{q.key}' [filter={meta_filters}]: {e}")
            return BaseAnswer(
                response=f"Error answering q={q.key}",
                page_numbers=[],
                confidence=0.0,
                confidence_explanation=str(e),
            )

    @task(task_run_name=generate_ask_run_name)
    def ask_group(
        self, questions: list[QuestionItem], meta_filters: dict[str, Any] = {}, **kwargs
    ) -> dict[str, BaseAnswer] | None:
        """Ask a group of questions in sequence. If the first question is affirmative
        then ask all the others. If the first question is negative, return None.

        Args:
            questions (list[QuestionItem]): List of Question Collection Items
            meta_filters (dict[str, Any], optional): Metadata filters for retrieval. Defaults to {}.

        Raises:
            ValueError: If the first question is not of type YES/NO

        Returns:
            dict[str, BaseAnswer] | None: A dictionary of the responses
        """
        # Check if the first question is of type YES/NO. If not, raise an error
        if questions[0].question_type != QuestionType.YES_NO:
            raise ValueError(
                "The first question of the group should be of type YES/NO. "
                f"Instead received {questions[0].question_type}"
            )

        responses = {}

        # Ask the 1st question
        q0 = questions[0]
        res = self.ask(q0, meta_filters, **kwargs)
        responses[q0.key] = res

        # Check if the response is of type YesNoEnum
        if not isinstance(res.response, YesNoEnum):
            raise ValueError(
                "The response of the first question should be of type YesNoEnum. "
                f"Instead received {type(res.response)}"
            )
        # If the response is affirmative, ask all the other questions
        if res.response.value == YesNoEnum.pos.value:
            for q in questions[1:]:
                responses[q.key] = self.ask(q, meta_filters, **kwargs)

        return responses

    @task(task_run_name="Q-Collection:{meta_filters}")
    def run_q_collection(
        self,
        q_collection: dict[str, list[QuestionItem]],
        meta_filters: dict[str, Any],
        pbar: bool = False,
        **kwargs,
    ) -> dict[str, QAResponse]:
        """Run the entire Q-collection and return the responses
        The Q-collection is a dictionary of lists of QuestionItems
        - The keys are the group names
        - The values are lists of QuestionItems
        - The QuestionItems are generated from the CSV and proto questions

        Args:
            q_collection (dict[str, list[QuestionItem]]): The Question Collection
            meta_filters (dict[str, Any]): Metadata filters for retrieval
            pbar (bool, optional): Whether to show a progress bar. Defaults to False.
        Raises:
            ValueError: If the first question of the group is not of type YES/NO
            ValueError: If the question type is not supported

        Returns:
            dict[str, QAResponse]: A dictionary of the responses
            - The keys are the question keys
            - The values are the QAResponse objects
            - The QAResponse objects contain the question, question_type and answer
            - The answer is a BaseAnswer object
        """
        # Run on the entire Q-collection
        questions_iter = tqdm(q_collection.items()) if pbar else q_collection.items()
        responses = {}
        # NOTE: Now the Q-collection is a 'dict[list[QuestionItem]]'
        for _, q_list in questions_iter:
            q = q_list[0]  # Get the first question of the group
            if pbar:
                questions_iter.set_description(q.key)

            if len(q_list) == 1:
                # A non-hierarchical question
                try:
                    answer = self.ask(q, meta_filters, **kwargs)
                    responses[q.key] = QAResponse(
                        question=q.question,
                        question_type=q.question_type,
                        answer=answer,
                    )
                except Exception as e:
                    print(f"❌ Error asking '{q.key}': {e}")

            elif len(q_list) > 1:
                # A hierarchical group of questions
                try:
                    group_responses = self.ask_group(q_list, meta_filters, **kwargs)
                    for i, (key, res) in enumerate(group_responses.items()):
                        responses[key] = QAResponse(
                            question=q_list[i].question,
                            question_type=q_list[i].question_type,
                            answer=res,
                        )
                except Exception as e:
                    logger.error(f"❌ Error asking group '{q.key}': {e}")

        return responses
