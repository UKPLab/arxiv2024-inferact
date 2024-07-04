import re, string, os
from typing import List
from enum import Enum
import tiktoken
from langchain import Wikipedia
from langchain.chat_models.base import BaseChatModel
from langchain.schema import messages_to_dict
from langchain.schema import (
    HumanMessage
)
from langchain.agents.react.base import DocstoreExplorer
from langchain.docstore.base import Docstore
from langchain.prompts import PromptTemplate
from llm import AnyOpenAILLM
from langchain.memory import ChatMessageHistory
from .prompts import (
    reflect_prompt,
    react_agent_prompt,
    react_reflect_agent_prompt,
    REFLECTION_HEADER,
    LAST_TRIAL_HEADER,
    REFLECTION_AFTER_LAST_TRIAL_HEADER
)

import os
import ipdb

from .fewshots import (
    WEBTHINK_SIMPLE6,
    REFLECTIONS)


class ReflexionStrategy(Enum):
    """
    NONE: No reflection
    LAST_ATTEMPT: Use last reasoning trace in context
    REFLEXION: Apply reflexion to the next reasoning trace
    LAST_ATTEMPT_AND_REFLEXION: Use last reasoning trace in context and apply reflexion to the next reasoning trace
    """

    NONE = "base"
    LAST_ATTEMPT = "last_trial"
    REFLEXION = "reflexion"
    ToM = "Theory_of_Mind"
    LAST_ATTEMPT_AND_REFLEXION = "last_trial_and_reflexion"
    WM = "world_model"
    NL = "nl"
    postNL = "post_nl"
    binary = "binary"
    postbinary = "post_binary"


class ReactAgent:
    def __init__(
        self,
        question: str,
        key: str,
        feedbacks: list = [],
        max_steps: int = 6,
        agent_prompt: PromptTemplate = react_reflect_agent_prompt,
        docstore: Docstore = Wikipedia(),
        react_llm: AnyOpenAILLM = AnyOpenAILLM(
            model_name="gpt4-turbo",
            model_kwargs={
                "stop": "\n",
                "temperature": 0.0,
                "max_tokens": 300},
        ),
    ) -> None:

        self.question = question
        self.answer = ""
        self.key = key
        self.max_steps = max_steps
        self.agent_prompt = agent_prompt
        self.react_examples = WEBTHINK_SIMPLE6
        self.feedbacks = feedbacks

        self.docstore = DocstoreExplorer(docstore)  # Search, Lookup
        self.llm = react_llm

        self.enc = tiktoken.encoding_for_model("text-davinci-003")

        self.__reset_agent()

    def run(self, reset=True) -> None:
        if reset:
            self.__reset_agent()

        while not self.is_halted() and not self.is_finished():
            self.step()

    def step(self) -> None:
        # ipdb.set_trace()
        # Think
        self.scratchpad += f"\nThought {self.step_n}:"
        self.scratchpad += " " + self.prompt_agent()
        # print(self.scratchpad.split("\n")[-1])

        # Act
        self.scratchpad += f"\nAction {self.step_n}:"
        action = self.prompt_agent()
        self.scratchpad += " " + action
        action_type, argument = parse_action(action)
        # print(self.scratchpad.split("\n")[-1])

        # Observe
        self.scratchpad += f"\nObservation {self.step_n}: "

        if action_type == "Finish":
            self.answer = argument
            if self.is_correct():
                self.scratchpad += "Answer is CORRECT"
            else:
                self.scratchpad += "Answer is INCORRECT"
            self.finished = True
            self.step_n += 1
            return

        if action_type == "Search":
            try:
                self.scratchpad += format_step(self.docstore.search(argument))
            except Exception as e:
                print(e)
                self.scratchpad += f"Could not find that page, please try again."

        elif action_type == "Lookup":
            try:
                self.scratchpad += format_step(self.docstore.lookup(argument))
            except ValueError:
                self.scratchpad += f"The last page Searched was not found, so you cannot Lookup a keyword in it. Please try one of the similar pages given."

        else:
            self.scratchpad += "Invalid Action. Valid Actions are Lookup[<topic>] Search[<topic>] and Finish[<answer>]."

        # print(self.scratchpad.split("\n")[-1])

        self.step_n += 1

    def prompt_agent(self) -> str:
        return format_step(self.llm([HumanMessage(content=self._build_agent_prompt())]))

    def _build_agent_prompt(self) -> str:
        if self.feedbacks:
            reflections_str = format_reflections(self.feedbacks)
        else:
            reflections_str = ""
        prompt = self.agent_prompt.format(
            examples=self.react_examples,
            question=self.question,
            reflections=reflections_str,
            scratchpad=self.scratchpad,
        )
        return prompt

    def is_finished(self) -> bool:
        return self.finished

    def is_correct(self) -> bool:
        return EM(self.answer, self.key)

    def is_halted(self) -> bool:
        return (
            (
                (self.step_n > self.max_steps)
                or (len(self.enc.encode(self._build_agent_prompt())) > 8000)
            )
            and not self.finished
            and not self.answer
        )

    def __reset_agent(self) -> None:
        self.step_n = 1
        self.finished = False
        self.scratchpad: str = ""

    def set_qa(self, question: str, key: str) -> None:
        self.question = question
        self.key = key

    def output_traj(self):
        history = ChatMessageHistory()
        history.add_user_message(f"Question: {self.question}")
        # remove the correctness judgement
        traj = "\n".join(self.scratchpad.split("\n")[:-1])
        history.add_ai_message(traj)

        return {
            "path": messages_to_dict(history.messages),
            "trace_correct": int(self.is_correct()),
            "is_halted": self.is_halted(),
            "predicted_answer": self.answer,
            "golden_answer": self.key,
            "reflection": self.feedbacks,
        }


# class ReactReflectAgent(ReactAgent):
#     def __init__(
#         self,
#         question: str,
#         key: str,
#         env_name: str = "",
#         max_steps: int = 6,
#         agent_prompt: PromptTemplate = react_reflect_agent_prompt,
#         reflect_prompt: PromptTemplate = reflect_prompt,
#         docstore: Docstore = Wikipedia(),
#         react_llm: AnyOpenAILLM = AnyOpenAILLM(
#             temperature=0,
#             max_tokens=300,
#             model_name="gpt4-turbo-128k",
#             model_kwargs={"stop": "\n"},
#             openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
#         ),
#         reflect_llm: AnyOpenAILLM = AnyOpenAILLM(
#             temperature=0,
#             max_tokens=300,
#             model_name="gpt4-turbo-128k",
#             openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
#         ),
#     ) -> None:

#         super().__init__(question, key, env_name, max_steps, agent_prompt, docstore, react_llm)
#         self.reflect_llm = reflect_llm
#         self.reflect_prompt = reflect_prompt
#         self.reflect_examples = REFLECTIONS
#         self.reflections: List[str] = []
#         self.reflections_str: str = ""
#         self.env_name = env_name

#     def run(
#         self,
#         reset=True,
#         reflect_strategy: ReflexionStrategy = ReflexionStrategy.REFLEXION,
#     ) -> None:
#         # if (self.is_finished() or self.is_halted()) and not self.is_correct():
#         self.reflect(reflect_strategy)
#         ReactAgent.run(self, reset)

#     def reflect(self, strategy: ReflexionStrategy) -> None:
#         print("Reflecting...")
#         if strategy == ReflexionStrategy.LAST_ATTEMPT:
#             self.reflections = [self.scratchpad]
#             self.reflections_str = format_last_attempt(
#                 self.question, self.reflections[0]
#             )
#         elif strategy == ReflexionStrategy.REFLEXION:
#             feedback_path = f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/gpt4-turbo/hotpotqa_post_feedback/binary/{self.env_name}.txt"
#             if os.path.exists(feedback_path):
#                 with open(feedback_path, 'r') as f:
#                     existing_reflections = f.readlines()
#                 existing_reflections = [r.strip() for r in existing_reflections]
#                 self.reflections = existing_reflections
    
#             reflection = self.prompt_reflection()
#             self.reflections += [reflection]

#             with open(feedback_path, 'w') as f:
#                 for reflection in self.reflections:
#                     f.write(reflection + '\n')

#             self.reflections_str = format_reflections(self.reflections)
#         elif strategy == ReflexionStrategy.LAST_ATTEMPT_AND_REFLEXION:
#             self.reflections_str = format_last_attempt(self.question, self.scratchpad)
#             self.reflections = [self.prompt_reflection()]
#             self.reflections_str += format_reflections(
#                 self.reflections, header=REFLECTION_AFTER_LAST_TRIAL_HEADER
#             )
#         elif strategy == ReflexionStrategy.NL:
#             with open(
#                 f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/gpt4-turbo/hotpotqa_feedback/{self.env_name}.txt",
#                 "r",
#             ) as f:
#                 self.reflections = f.readlines()
#             self.reflections_str = format_reflections(self.reflections)
#         elif strategy == ReflexionStrategy.postNL:
#             with open(
#                 f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/gpt4-turbo/hotpotqa_post_feedback/NL/{self.env_name}.txt",
#                 "r",
#             ) as f:
#                 self.reflections = f.readlines()
#             self.reflections_str = format_reflections(self.reflections)

#         else:
#             raise NotImplementedError(f"Unknown reflection strategy: {strategy}")

#     def prompt_reflection(self) -> str:
#         return format_step(
#             self.reflect_llm([HumanMessage(content=self._build_reflection_prompt())])
#         )

#     def output_traj(self):
#         history = ChatMessageHistory()
#         history.add_user_message(f"Question: {self.question}")
#         # remove the correctness judgement
#         traj = "\n".join(self.scratchpad.split("\n")[:-1])
#         history.add_ai_message(traj)

#         return {
#             "path": messages_to_dict(history.messages),
#             "trace_correct": int(self.is_correct()),
#             "is_halted": self.is_halted(),
#             "predicted_answer": self.answer,
#             "golden_answer": self.key,
#             "reflection": self.reflections,
#         }

#     def _build_reflection_prompt(self) -> str:
#         return self.reflect_prompt.format(
#             examples=self.reflect_examples,
#             question=self.question,
#             scratchpad=truncate_scratchpad(self.scratchpad, tokenizer=self.enc),
#         )

#     def _build_agent_prompt(self) -> str:
#         return self.agent_prompt.format(
#             examples=self.react_examples,
#             reflections=self.reflections_str,
#             question=self.question,
#             scratchpad=self.scratchpad,
#         )

### String Stuff ###
gpt2_enc = tiktoken.encoding_for_model("text-davinci-003")


def parse_action(string):
    pattern = r"^(\w+)\[(.+)\]$"
    match = re.match(pattern, string)

    if match:
        action_type = match.group(1)
        argument = match.group(2)
        return action_type, argument

    else:
        return None, None


def format_step(step: str) -> str:
    return step.strip("\n").strip().replace("\n", "")


def format_tom_output(step: str) -> str:
    splitted = step.split(
        "Based on the given trajectory, I think the question the agent answered is:"
    )[1]
    tom_question = splitted.split("The reason is as follows:")[0].strip()
    question_reason = splitted.split("The reason is as follows:")[1].strip()
    return tom_question, question_reason


def format_judge_output(step: str) -> str:
    answers = step.split("Answer:")[1].split("The reason is:")
    answer = answers[0].strip("\n").strip()
    reason = answers[1].strip("\n").strip()
    return answer, reason


def format_reflections(reflections: List[str], header: str = REFLECTION_HEADER) -> str:
    if reflections == []:
        return ""
    else:
        return (
            header + "Reflections:\n- " + "\n- ".join([r.strip() for r in reflections])
        )


def format_last_attempt(
    question: str, scratchpad: str, header: str = LAST_TRIAL_HEADER
):
    return (
        header
        + f"Question: {question}\n"
        + truncate_scratchpad(scratchpad, tokenizer=gpt2_enc).strip("\n").strip()
        + "\n(END PREVIOUS TRIAL)\n"
    )


def truncate_scratchpad(
    scratchpad: str, n_tokens: int = 1600, tokenizer=gpt2_enc
) -> str:
    lines = scratchpad.split("\n")
    observations = filter(lambda x: x.startswith("Observation"), lines)
    observations_by_tokens = sorted(
        observations, key=lambda x: len(tokenizer.encode(x))
    )
    while len(gpt2_enc.encode("\n".join(lines))) > n_tokens:
        largest_observation = observations_by_tokens.pop(-1)
        ind = lines.index(largest_observation)
        lines[ind] = (
            largest_observation.split(":")[0] + ": [truncated wikipedia excerpt]"
        )
    return "\n".join(lines)


def extract_action(scratchpad, tokenizer=gpt2_enc, n_tokens: int = 2048) -> str:
    lines = scratchpad.split("\n")
    actions = list(filter(lambda x: x.startswith("Action"), lines))
    observations = list(filter(lambda x: x.startswith("Observation"), lines))
    remaining_action = actions[len(observations) :]
    # concat actions and observations interleaved
    actions_obs = [
        val for pair in zip(actions, observations) for val in pair
    ] + remaining_action
    observations_by_tokens = sorted(
        observations, key=lambda x: len(tokenizer.encode(x))
    )
    while len(gpt2_enc.encode("\n".join(actions_obs))) > n_tokens:
        largest_observation = observations_by_tokens.pop(-1)
        ind = actions_obs.index(largest_observation)
        actions_obs[ind] = (
            largest_observation.split(":")[0] + ": [truncated wikipedia excerpt]"
        )
    return "\n".join(actions_obs)


def normalize_answer(s):
    def remove_articles(text):
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def EM(answer, key) -> bool:
    answer = normalize_answer(answer)
    key = normalize_answer(key)
    return answer == key or (key in answer or answer in key and answer != "")
