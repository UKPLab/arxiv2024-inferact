"""Adapted from https://github.com/ysymyth/ReAct/blob/master/alfworld.ipynb"""

import os
import sys
import json
import yaml
import importlib
import alfworld
import alfworld.agents.environment
import ipdb
from tqdm import tqdm
# from utils import Model, get_chat, get_completion
from .env_history import EnvironmentHistory
sys.path.append(os.path.abspath('../../'))
from llm import AnyOpenAILLM
from typing import List, Dict, Any, Tuple
from langchain.schema import messages_to_dict
import ipdb

FOLDER = './actor/alfworld/prompts'
PROMPT_FILE = 'alfworld_3prompts.json'
with open(os.path.join(FOLDER, PROMPT_FILE), 'r') as f:
    examples = json.load(f)

def llm(prompt: str, model, stop: List[str] = ["\n"]):
    try:
        cur_try = 0
        while cur_try < 6:
            text = model(prompt)
            # dumb way to do this
            if len(text.strip()) >= 5:
                return text
            cur_try += 1
        return ""
    except Exception as e:
        # print(prompt)
        print(e)
        import sys
        sys.exit(1)

def process_ob(ob):
    if ob.startswith('You arrive at loc '):
        ob = ob[ob.find('. ')+2:]    
    return ob

def alfworld_run(env, base_prompt, memory: List[str], model: AnyOpenAILLM, to_print=True, ob='') -> Tuple[EnvironmentHistory, bool]:
    if len(memory) > 3:
        env_history = EnvironmentHistory(base_prompt, ob, memory[-3:], [])
    else:
        env_history = EnvironmentHistory(base_prompt, ob, memory, [])
    env_history.reset()
    if to_print:
        print(ob)
        sys.stdout.flush()
    cur_step = 0
    while cur_step < 49:
        # ipdb.set_trace()
        action = llm(env_history.messages, model, stop=['\n']).strip()
        env_history.add("action", action)
        # remove > from action
        if action.startswith('> '):
            normalized_action = action[2:]
        observation, reward, done, info = env.step([normalized_action])
        observation, reward, done = process_ob(observation[0]), info['won'][0], done[0]
        # ipdb.set_trace()
        if action.startswith('> think:'):
            observation = 'OK.'
        env_history.add("observation", observation)
        if to_print:
            print(f'{action}\n{observation}')
            sys.stdout.flush()
        if done:
            return env_history, True
        elif env_history.check_is_exhausted():
            return env_history, False
        cur_step += 1
    return env_history, False

PREFIXES = {
    'pick_and_place': 'put',
    'pick_clean_then_place': 'clean',
    'pick_heat_then_place': 'heat',
    'pick_cool_then_place': 'cool',
    'look_at_obj': 'examine',
    'pick_two_obj': 'puttwo'
}

def run_trial(
        trial_log_dir: str,
        env_configs: List[Dict[str, Any]],
        use_memory: bool,
        model_name: str,
    ) -> List[Dict[str, Any]]:
    importlib.reload(alfworld)
    importlib.reload(alfworld.agents.environment)

    with open('base_config.yaml') as reader:
        config = yaml.safe_load(reader)
    split = "eval_out_of_distribution"

    env = getattr(alfworld.agents.environment, config["env"]["type"])
    env = env(config, train_eval=split)
    env = env.init_env(batch_size=1)
    model = AnyOpenAILLM(model_name=model_name, stop=["\n"], temperature=0.0)

    num_envs: int = len(env_configs)
    path = {}
    files = os.listdir(trial_log_dir)
    existing_interactions = []
    if files:
        existing_interactions = [f for f in files if f.endswith('.json')]
        print('existing num', len(existing_interactions))
    # ipdb.set_trace()
    for z, env_config in tqdm(enumerate(env_configs)):
        ob, info = env.reset()

        ob = '\n'.join(ob[0].split('\n\n')[1:])
        name = '/'.join(info['extra.gamefile'][0].split('/')[-3:-1])
        print(f"using {name}")

        if env_config["is_success"]:
            continue
        if f"{z}.json" in existing_interactions:
            continue
        
        for i, (k, v) in enumerate(PREFIXES.items()):
            if name.startswith(k):
                base_prompt = 'You are interacting with a household to solve a task. After your each turn, the environment will give you immediate feedback. If the environment output "Nothing happens", that means the previous action is invalid and you should try more options. Here are two examples to help you understand the task.\n' + examples[f'react_{v}_1'] + examples[f'react_{v}_0'] + '(END OF EXAMPLES)\nYou MUST follow the format of the examples above to solve the task.\n'
                final_env_history, is_success = alfworld_run(env, base_prompt, env_config["memory"] if use_memory else [], to_print=True, ob=ob, model=model)
                # update env config
                if is_success:
                    env_configs[z]['is_success'] = True

                path['env_name'] = name
                path['info'] = info
                path['path'] = messages_to_dict(final_env_history.messages)
                path['trace_correct'] = is_success
                # log env results to trial log
                with open(os.path.join(trial_log_dir, f'{z}.json'), 'w') as wf:
                    json.dump(path, wf, indent=4)
                    # wf.write(f'\n#####\n\nEnvironment #{z}:\n{final_env_history}\n\nSTATUS: {"OK" if is_success else "FAIL"}\n\n#####\n')

    # close environment object
    env.close()

    return env_configs
