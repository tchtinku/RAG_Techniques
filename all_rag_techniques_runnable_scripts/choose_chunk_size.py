import nest_asyncio
import random
import time
import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.prompts import PromptTemplate
from llama_index.core.evaluation import DatasetGenerator, FaithfulnessEvaluator, RelevancyEvaluator
from llama_index.llms.openai import OpenAI

# Apply asyncio fix for Jupyter notebooks
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Set the OpenAI API key environment variable
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')


# Utility functions
def evaluate_response_time_and_accuracy(chunk_size, eval_questions, eval_documents, faithfulness_evaluator,
                                        relevancy_evaluator):
    """
    Evaluate the average response time, faithfulness, and relevancy of responses generated by GPT-3.5-turbo for a given chunk size.

    Parameters:
    chunk_size (int): The size of data chunks being processed.
    eval_questions (list): List of evaluation questions.
    eval_documents (list): Documents used for evaluation.
    faithfulness_evaluator (FaithfulnessEvaluator): Evaluator for faithfulness.
    relevancy_evaluator (RelevancyEvaluator): Evaluator for relevancy.

    Returns:
    tuple: A tuple containing the average response time, faithfulness, and relevancy metrics.
    """

    total_response_time = 0
    total_faithfulness = 0
    total_relevancy = 0

    # Set global LLM as GPT-3.5 
    llm = OpenAI(model="gpt-3.5-turbo")
    Settings.llm = llm
    
    # Create vector index
    vector_index = VectorStoreIndex.from_documents(eval_documents)

    # Build query engine
    query_engine = vector_index.as_query_engine(similarity_top_k=5)
    num_questions = len(eval_questions)

    # Iterate over each question in eval_questions to compute metrics
    for question in eval_questions:
        start_time = time.time()
        response_vector = query_engine.query(question)
        elapsed_time = time.time() - start_time

        faithfulness_result = faithfulness_evaluator.evaluate_response(response=response_vector).passing
        relevancy_result = relevancy_evaluator.evaluate_response(query=question, response=response_vector).passing

        total_response_time += elapsed_time
        total_faithfulness += faithfulness_result
        total_relevancy += relevancy_result

    average_response_time = total_response_time / num_questions
    average_faithfulness = total_faithfulness / num_questions
    average_relevancy = total_relevancy / num_questions

    return average_response_time, average_faithfulness, average_relevancy


# Define the main class for the RAG method

class RAGEvaluator:
    def __init__(self, data_dir, num_eval_questions, chunk_sizes):
        self.data_dir = data_dir
        self.num_eval_questions = num_eval_questions
        self.chunk_sizes = chunk_sizes
        self.documents = self.load_documents()
        self.eval_questions = self.generate_eval_questions()
        # Set GPT-4o as local configuration for evaluation
        self.llm_gpt4 = OpenAI(model="gpt-4o")
        self.faithfulness_evaluator = self.create_faithfulness_evaluator()
        self.relevancy_evaluator = self.create_relevancy_evaluator()

    def load_documents(self):
        return SimpleDirectoryReader(self.data_dir).load_data()

    def generate_eval_questions(self):
        eval_documents = self.documents[0:20]
        data_generator = DatasetGenerator.from_documents(eval_documents)
        eval_questions = data_generator.generate_questions_from_nodes()
        return random.sample(eval_questions, self.num_eval_questions)


    def create_faithfulness_evaluator(self):
        faithfulness_evaluator = FaithfulnessEvaluator(llm=self.llm_gpt4)
        faithfulness_new_prompt_template = PromptTemplate("""
            Please tell if a given piece of information is directly supported by the context.
            You need to answer with either YES or NO.
            Answer YES if any part of the context explicitly supports the information, even if most of the context is unrelated. If the context does not explicitly support the information, answer NO. Some examples are provided below.
            ...
            """)
        faithfulness_evaluator.update_prompts({"your_prompt_key": faithfulness_new_prompt_template})
        return faithfulness_evaluator

    def create_relevancy_evaluator(self):
        return RelevancyEvaluator(llm=self.llm_gpt4)

    def run(self):
        for chunk_size in self.chunk_sizes:
            avg_response_time, avg_faithfulness, avg_relevancy = evaluate_response_time_and_accuracy(
                chunk_size,
                self.eval_questions,
                self.documents[0:20],
                self.faithfulness_evaluator,
                self.relevancy_evaluator
            )
            print(f"Chunk size {chunk_size} - Average Response time: {avg_response_time:.2f}s, "
                  f"Average Faithfulness: {avg_faithfulness:.2f}, Average Relevancy: {avg_relevancy:.2f}")


# Argument Parsing

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description='RAG Method Evaluation')
    parser.add_argument('--data_dir', type=str, default='../data', help='Directory of the documents')
    parser.add_argument('--num_eval_questions', type=int, default=25, help='Number of evaluation questions')
    parser.add_argument('--chunk_sizes', nargs='+', type=int, default=[128, 256], help='List of chunk sizes')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluator = RAGEvaluator(data_dir=args.data_dir, num_eval_questions=args.num_eval_questions,
                             chunk_sizes=args.chunk_sizes)
    evaluator.run()