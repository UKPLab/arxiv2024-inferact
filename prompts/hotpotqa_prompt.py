hotpot_k_task_inference = """You have a powerful Theory-of-Mind capability. A reasoning agent is answering the user's question using the following tools:
(1) Search[entity], which searches the exact entity on Wikipedia and returns the first paragraph if it exists. If not, it will return some similar entities to search.
(2) Lookup[keyword], which returns the next sentence containing keyword in the last passage successfully found by Search.
(3) Finish[answer], which returns the answer to the question and finishes the task.
I will give you the reasoning trajectory the agent takes. Your task is to infer the {num_tasks} most likely questions that the reasoning trajectory solved.
Remember your inferred questions should be as diverse as possible and semantically different from each other.
Your response MUST use the following format: 
The {num_tasks} most likely questions are: <A. question1\nB. question2\nC. question3>
The reason is: <the reason you think>.

The reasoning trajectory the agent takes is {action}."""

hotpot_task_validator = """You are a powerful judge of agent-based question answering. An agent, Actor, is helping the user to answer questions using following tools:
(1) Search[entity], which searches the exact entity on Wikipedia and returns the first paragraph if it exists. If not, it will return some similar entities to search.
(2) Lookup[keyword], which returns the next sentence containing keyword in the last passage successfully found by Search.
(3) Finish[answer], which returns the answer to the question and finishes the task.
I will give you the reasoning trajectory performed by the agent and a set of questions, your task is to select your top {num} guesses and assign a probability (ranging from 0.0 to 1.0) to each, indicating the likelihood that the question is solved by the reasoning trajectory.
Your response MUST follow the format: 
G1: <Only output the option label of the question that you think is correct. No other words or explanation.> P1: <the probability of the question being correct> ... G_i: <Only output the option label of the question that you think is correct. No other words or explanation> P_i: <the probability of the question i being correct>
Justification:<A brief justification for your response>

The reasoning trajectory is {action}
The candidate questions are as follows:
{instructions}"""

hotpot_standard_eval = """You will be given the question and the reasoning trajectory you performed to find the answer to the question. Your task is to evaluate the reasoning trajectory and determine how likely it is to be correct. You need to assign a probability (ranging from 0.0 to 1.0) to your response, indicating the likelihood that the reasoning trajectory is correct.
Your response MUST follow the format:
The answer is: <Correct/Incorrect>
Confidence: <A probability ranging from 0.0 to 1.0>
Justification: <A brief justification for your response>

The question is: {instruction}
The reasoning trajectory is {trajectory}"""

hotpot_multi_step = """You will be given the reasoning trajectory you performed in a question answering task for a given question. Your task is to evaluate the reasoning trajectory step by step and determine how likely each step is correct. 
Each step has three parts: Thought, Action, and Observation. You need to assign a probability (ranging from 0.0 to 1.0) to each step, indicating the likelihood that the step is correct.

Your response should follow the format:
Step 1: <A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step 1 is correct>\nStep 2:<A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step 2 is correct>\n ... \nStep i: <A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step i is correct>
Justification: <A brief justification for your response. No more than six sentences.>

The instruction is: {instruction}
The reasoning trajectory is {trajectory}"""

hot_feedback_prompt = """An Actor agent is answering the user's question using some search tools. I will give you the user's question, the correct answer that the user is looking for, and the incorrect action chain performed by the Actor agent. 
You need to imagine that you are the user and provide feedback to help the Actor agent find the correct answer. Your feedback should be constructive and specific. Please provide your feedback in the following format:
Feedback: <Your feedback to help the Actor agent find the correct answer. It should be clear, concise, and no more than five sentences.>
Your (the user's) question is: {task}
The correct answer is: {gold_label_actor}
The incorrect action chain is: {incorrect_action_chain}"""

hot_afterwards_feedback_prompt = """An Actor agent is answering the user's question using search tools. You've already provided feedback to help the agent find the correct answer. However, the Actor agent still failed. I will give you the user's question, the correct answer that the user is looking for, and the incorrect action chain performed by the Actor agent. 
You need to imagine that you are the user and provide feedback to help the Actor agent find the correct answer. Your feedback should be constructive and specific. Please provide your feedback in the following format:
Feedback: <Your feedback to help the Actor agent find the correct answer. It should be clear, concise, and no more than five sentences.>
Your (the user's) question is: {task}
The correct answer is: {gold_label_actor}
The incorrect action chain is: {incorrect_action_chain}
The feedback(s) you provided before are: {previous_feedback}"""

hotpot_binary_feedback_prompt = """You are an advanced reasoning agent that can improve based on self refection. You will be given a previous reasoning trial in which you were given access to an Docstore API environment and a question to answer. You were unsuccessful in answering the question either because you guessed the wrong answer with Finish[<answer>], or you used up your set number of reasoning steps. In a few sentences, Diagnose a possible reason for failure and devise a new, concise, high level plan that aims to mitigate the same failure. Use complete sentences.  
Here are some examples:
{examples}
(END OF EXAMPLES)

Previous trial:
Question: {question}{scratchpad}

Reflection:"""