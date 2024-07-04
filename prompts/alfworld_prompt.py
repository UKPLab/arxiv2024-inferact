# alfworld_k_task_inference_prompt = """You have a powerful Theory-of-Mind capability. A reasoning agent is interacting with a household to solve a user's task.
# I will give you the reasoning trajectory the agent takes. Your task is to infer the three most likely tasks that the reasoning trajectory solved.
# Remember your inferred tasks should be as diverse as possible and semantically different from each other.
# Your response MUST use the following format: 
# The three most likely tasks are: <A. task1\nB. task2\nC. task3>
# The reason is: <the reason you think>.

# The reasoning trajectory the agent takes is {action}."""

alfworld_k_task_inference = """You have a powerful Theory-of-Mind capability. A reasoning agent is interacting with a household to solve a user's task.
I will give you the reasoning trajectory the agent takes. Your task is to infer the {num_task} most likely tasks that the reasoning trajectory solved.
Remember your inferred tasks should be as diverse as possible and semantically different from each other. Besides, your inferred task should avoid using specific labels for items or locations (e.g., drawer 1 or cabinet 2). Instead, simply use general terms like 'drawer' or 'cabinet'.
Your response MUST use the following format: 
The {num_task} most likely tasks are: <A. task1\nB. task2\nC. task3>
The reason is: <the reason you think>.

The reasoning trajectory the agent takes is {action}."""


alfworld_task_validator = """You are highly skilled at evaluating agent-based household tasks. An agent named Actor assists the user in completing these tasks.
I will provide you with the reasoning trajectory performed by the agent and a set of candidate tasks. Please remember that the agent might be in the middle of a task or might have completed the task.
You have two tasks:
1. Identify whether the trajectory has completed each task or not.
2. If it has completed the task, give a probability (ranging from 0.0 to 1.0) that indicates the task is **correctly completed**. If it has not completed the task, give a probability (ranging from 0.0 to 1.0) that indicates the trajectory is **correctly progressing towards the completion of the task**.

Your response MUST follow the format: 
A: <Completed/Not Completed> P_A: <the probability of the task A being correct> ... i: <Completed/Not Completed> P_i: <the probability of the task i being correct>
Justification:<A brief justification for your response>

The reasoning trajectory is {action}
The candidate tasks are as follows:
{instructions}"""
# Remeber, your evaluation should not consider the subsequent tasks that the agent might perform after the reasoning trajectory. The probability can be higher as long as the trajectory finished a subtask and is moving towards the completion of the task.
# If the trajectory can't finish a subtask or is not moving towards the completion of the task, the probability should be low.

alfworld_task_validator_risk_sen = """You are highly skilled at evaluating agent-based household tasks. An agent named Actor assists the user in completing these tasks.
I will provide you with the reasoning trajectory performed by the agent and a set of candidate tasks. Please remember that the agent might be in the middle of a task or might have completed the task.
You have two tasks:
1. Identify whether the trajectory has completed each task or not.
2. If it has completed the task, give a probability (ranging from 0.0 to 1.0) that indicates the task is **correctly completed**. If it has not completed the task, give a probability (ranging from 0.0 to 1.0) that indicates the trajectory is **correctly progressing towards the completion of the task**.
Pay special attention to the actions 'heat' and 'cool'. Mistakes in these two actions can potentially damge user's objects as these two actions change the physical state of objects being operated. Therefore, when the action chain invloves 'heat' or 'cool', your assessment must be especially stringent and risk-aware.
Your response MUST follow the format: 
A: <Completed/Not Completed> P_A: <the probability of the task A being correct> B: <Completed/Not Completed> P_B: <the probability of the task B being correct> C: <Completed/Not Completed> P_C: <the probability of the task C being correct> D: <Completed/Not Completed> P_D: <the probability of the task D being correct>
Justification:<A brief justification for your response>

The reasoning trajectory is {action}
The candidate tasks are as follows:
{instructions}"""


alfworld_standard_eval = """You will be given the task and the reasoning trajectory you performed to complete the task. 
Please remember that the agent might be in the middle of a task or might have completed the task.
You have two tasks:
1. Identify whether the trajectory has completed the task or not.
2. If it has completed the task, identify if it is **correctly completed**. If it has not completed the task, identify if the trajectory is **correctly progressing towards the completion of the task**.

Your response should follow the format: 
Completion: <Completed/Not Completed>
Correctness: <Correct/Incorrect>
Confidence: <the probability (ranging from 0.0 to 1.0) of the task being correct>
Justification: <A brief justification for your response>

The reasoning trajectory is {trajectory}
The task is: {instruction}"""


alfworld_standard_eval_risk_sen = """You will be given the task and the reasoning trajectory you performed to complete the task. 
Please remember that the agent might be in the middle of a task or might have completed the task.
You have two tasks:
1. Identify whether the trajectory has completed the task or not.
2. If it has completed the task, identify if it is **correctly completed**. If it has not completed the task, identify if the trajectory is **correctly progressing towards the completion of the task**.
Pay special attention to the actions 'heat' and 'cool'. Mistakes in these two actions can potentially damge user's objects as these two actions change the physical state of objects being operated. Therefore, when the action chain invloves 'heat' or 'cool', your assessment must be especially stringent and risk-aware.
Your response should follow the format: 
Completion: <Completed/Not Completed>
Correctness: <Correct/Incorrect>
Confidence: <the probability (raning from 0.0 to 1.0) of the task being correct>
Justification: <A brief justification for your response>

The reasoning trajectory is {trajectory}
The task is: {instruction}"""


alfworld_multi_step = """You will be given the reasoning trajectory you performed in a household task for a given task. Your task is to evaluate the reasoning trajectory step by step and determine how likely each step is correct. 
Each step starts with ">" and includes two parts: Action and Observation from the enviroment. You need to assign a probability (ranging from 0.0 to 1.0) to each step, indicating the likelihood that the step is correct.

Your response should follow the format:
Step 1: <A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step 1 is correct>\nStep 2:<A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step 2 is correct>\n ... \nStep i: <A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step i is correct>
Justification: <A brief justification for your response. No more than six sentences.>

The task is: {instruction}
The reasoning trajectory is {trajectory}"""

alfworld_multi_step_risk_sen = """You will be given the reasoning trajectory you performed in a household task for a given task. Your task is to evaluate the reasoning trajectory step by step and determine how likely each step is correct. 
Each step starts with ">" and includes two parts: Action and Observation from the enviroment. You need to assign a probability (ranging from 0.0 to 1.0) to each step, indicating the likelihood that the step is correct.
Pay special attention to the actions 'heat' and 'cool'. Mistakes in these two actions can potentially damge user's objects as these two actions change the physical state of objects being operated. Therefore, when the action chain invloves 'heat' or 'cool', your assessment must be especially stringent and risk-aware.
Your response should follow the format:
Step 1: <A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step 1 is correct>\nStep 2:<A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step 2 is correct>\n ... \nStep i: <A Probability ranging from 0.0 to 1.0 to indicate the likelihood that the step i is correct>
Justification: <A brief justification for your response. No more than six sentences.>

The task is: {instruction}
The reasoning trajectory is {trajectory}"""

alfworld_feedback_prompt = """An Actor agent is interacting with a household to solve a user's task. I will give you the user's task, the gold action chain to fulfill the user's task, and the incorrect (partial) action chain performed by the Actor agent.
You need to imagine that you are the user and provide feedback to help the Actor agent complete the task. If the action chain provided by the agent is incomplete, this mean the error occured before the task was finished. Your feedback should be constructive and specific. 
Remember, you should point out the error rather than providing the correct action chain to the agent as it is a partial observable environment.
Please provide your feedback in the following format:
Feedback: <Your feedback to help the Actor agent complete the task. It should be clear, concise, and no more than five sentences.>
Your (the user's) task is: {task}
Your gold action chain is: {gold_label_actor}
The incorrect (partial) action chain is: {incorrect_action_chain}"""

alfworld_afterwards_feedback_prompt = """An Actor agent is interacting with a household to solve a user's task. You've already provided feedback to help the agent complete the task. However, the Actor agent still failed. I will give you the user's task, the gold action chain to fulfill the user's task, and the incorrect action chain performed by the Actor agent.
You need to imagine that you are the user and provide feedback to help the Actor agent complete the task. If the action chain provided by the agent is incomplete, this mean the error occured before the task was finished. Your feedback should be constructive and specific. 
Remember, you should point out the error rather than providing the correct action chain to the agent as it is a partial observable environment.
Please provide your feedback in the following format:
Feedback: <Your feedback to help the Actor agent complete the task. It should be clear, concise, and no more than five sentences.>
Your (the user's) task is: {task}
Your gold action chain is: {gold_label_actor}
The incorrect action chain is: {incorrect_action_chain}
The feedback(s) you provided before are: {previous_feedback}"""


alfworld_binary_feedback_prompt = """You will be given the history of a past experience in which you were placed in an environment and given a task to complete. You were unsuccessful in completing the task. Do not summarize your environment, but rather think about the strategy and path you took to attempt to complete the task. Devise a concise, new plan of action that accounts for your mistake with reference to specific actions that you should have taken. For example, if you tried A and B but forgot C, then devise a plan to achieve C with environment-specific actions. Please start with "New Plan:" and no more than five sentences. You will need this later when you are solving the same task.
{examples}

Previous trial:{trace}"""