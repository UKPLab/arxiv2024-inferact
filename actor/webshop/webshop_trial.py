import os
import sys
import openai
import requests
from bs4 import BeautifulSoup
from bs4.element import Comment
from .env_history import EnvironmentHistory
from langchain.schema import messages_to_dict
from .web_agent_site.envs.web_agent_text_env import WebAgentTextEnv
sys.path.append(os.path.abspath('../../'))
from llm import AnyOpenAILLM
from typing import Any, Dict, List, Tuple
import re
import json

BASE_PROMPT = """
You are web shopping.
I will give you instructions about what to do.
You have to follow the instructions.
Every round I will give you an observation and a list of available actions, \
you have to respond an action based on the state and instruction.
You can use search action if search is available.
You can click one of the buttons in clickables.
An action should be of the following structure:
search[keywords]
click[value]
If the action is not valid, perform nothing.
Keywords in search are up to you, but the value in click MUST be a value in the list 'clickables' of the 'Available Actions' provided in the observation (e.g. Prev/Next, Back to search, Options, Buy Now).
Remember that your keywords in search should be carefully designed. If you cannot find the item with the detailed query, you should simplify the query to recall more results and then explore them.
There are some website design features you should remeber in mind.
1. On the product page, after you select a certain feature (e.g. size, color), the page will not change but the feature is indeed selected.
2. All clickable options on the product page are available to purchase. So there is no need to check the stock or availability.

Your response should use the following format:

Thought:
<Your idea to complete the instruction.>

Action:
<The action you will take based on your thought. Each time you can take ONLY one action.>"""




def llm(prompt: str, model):
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

def webshop_run(env, base_prompt, memory: List[str], model: AnyOpenAILLM) -> Tuple[EnvironmentHistory, int, Dict, Dict, bool]:
    init_prompt = base_prompt
    prompt = ''

    env_history = EnvironmentHistory(base_prompt)
    env_history.reset()

    # add one-shot example
    env_history.add("action", "Ok.")
    env_history.add("observation", 'Observation:\nWebShop [SEP] Instruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Search\n\nAvailable Actions:\n{"has_search_bar": true, "clickables": ["..."]}')
    env_history.add("action", 'Thought:\nI think I should use the search bar to look for the product I need.\n\nAction:\nsearch[l\'eau d\'issey 6.76 fl oz bottle price < 100.00]')
    env_history.add("observation",'Observation:\nInstruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Back to Search [SEP] Page 1 (Total results: 50) [SEP] Next > [SEP] B000VOHH8I [SEP] L\'eau D\'issey By Issey Miyake for MenEau De Toilette Spray, 6.7 Fl Oz Bottle [SEP] $64.98 [SEP] B000MJZOPK [SEP] L\'eau d\'Issey by Issey Miyake for Women 3.3 oz Eau de Toilette Spray [SEP] $49.98 [SEP] B0012S249E [SEP] L\'eau D\'issey By Issey Miyake For Women. Shower Cream 6.7-Ounces [SEP] $31.36 [SEP] B01H8PGKZS [SEP] L\'eau D\'Issey FOR MEN by Issey Miyake - 6.7 oz EDT Spray [SEP] $67.97 [SEP] B00G3C8FHE [SEP] L\'Eau d\'Issey pour Homme - Eau de Toilette 4.2 fl oz [SEP] $51.25 [SEP] B000R94HRG [SEP] Issey Miyake L\'Eau D\'Issey Pour Homme Eau De Toilette Natural Spray [SEP] $44.99 [SEP] B000C214CO [SEP] Issey Miyake L\'eau D\'issey Eau de Toilette Spray for Men, 4.2 Fl Oz [SEP] $53.99 [SEP] B0018SBRDC [SEP] Issey Miyake L\'eau d\'Issey for Women EDT, White, 0.84 Fl Oz [SEP] $27.04 [SEP] B000XEAZ9Y [SEP] L\'eau De Issey By Issey Miyake For Men. Eau De Toilette Spray 6.7 Fl Oz [SEP] $67.08 [SEP] B079HZR2RX [SEP] L\'eau d\'Issey Pure by Issey Miyake for Women 3.0 oz Nectar de Parfum Spray [SEP] $71.49\n\nAvailable Actions:\n{"has_search_bar": false, "clickables": ["...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "..."]}')
    env_history.add("action",'Thought:\nI think I should click on the product I need, which is B000VOHH8I.\n\nAction:\nclick[B000VOHH8I]')
    env_history.add("observation",'Observation:\nInstruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Back to Search [SEP] < Prev [SEP] size [SEP] 2.5 fl oz [SEP] 6.76 fl oz (pack of 1) [SEP] L\'eau D\'issey By Issey Miyake for MenEau De Toilette Spray, 6.7 Fl Oz Bottle [SEP] Price: $64.98 [SEP] Rating: N.A. [SEP] Description [SEP] Features [SEP] Reviews [SEP] Buy Now\n\nAvailable Actions:\n{"has_search_bar": false, "clickables": ["Back to Search", "< Prev", "Description", "Features", "Reviews", "Buy Now", "2.5 fl oz", "6.76 fl oz (pack of 1)"]}')
    env_history.add("action",'Thought:\nI think I should click on the \'6.76 fl oz (pack of 1)\' option to select the size I need.\n\nAction:\nclick[6.76 fl oz (pack of 1)]')
    env_history.add("observation",'Observation:\nInstruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Back to Search [SEP] < Prev [SEP] size [SEP] 2.5 fl oz [SEP] 6.76 fl oz (pack of 1) [SEP] L\'eau D\'issey By Issey Miyake for MenEau De Toilette Spray, 6.7 Fl Oz Bottle [SEP] Price: $64.98 [SEP] Rating: N.A. [SEP] Description [SEP] Features [SEP] Reviews [SEP] Buy Now\n\nAvailable Actions:\n{"has_search_bar": false, "clickables": ["Back to Search", "< Prev", "Description", "Features", "Reviews", "Buy Now", "2.5 fl oz", "6.76 fl oz (pack of 1)"]}')
    env_history.add("action",'Thought:\nI think I should click on the \'Buy Now\' button to purchase the product.\n\nAction:\nclick[Buy Now]')
    observation = env.observation
    env_history.add_new_task(observation, memory)

    num_actions = 0
    is_terminal = False
    while num_actions < 15 and not is_terminal:
        response = llm(env_history.messages, model).strip()
        action = re.search(
                    r"[Aa]ction:(\s|\n)*((search|click)\[.+?])", response
                ).group(2)
        try:
            observation, reward, done, info = env.step(action)
            if not observation.startswith("Observation"):
                observation = "Observation:\n" + observation

        except AssertionError:
            observation, reward, done, info = env.observation, 0, False, ""
        
        # available_actions = env.get_available_actions()
        env_history.add("action", response)
        env_history.add("observation", observation)

        # is_terminal = identify_terminal(response, observation)
        num_actions += 1
        if done:
            break
        
        # if done, check if reward is complete value
    
    if num_actions == 15 and "Thank you for shopping with us!" not in observation:
        is_halted = True
    else:
        is_halted = False

    try:
        reward_info = env.server.user_sessions[
                str(env.session)
            ]["verbose_info"]

    except:
        reward_info = None
    
    true_item = env.server.goals[int(env.session)]

    return env_history, reward == 1.0, reward_info, true_item, is_halted

# def identify_terminal(response: str, observation: str) -> bool:
#     try:
#         return "click[Buy Now]" in response and "click[Buy Now] is not valid. Please check it again!" not in observation
#     except:
#         return True

def run_webshop(
        trial_log_dir: str,
        env_configs: List[Dict[str, Any]],
        model_name: str,
    ) -> List[Dict[str, Any]]:
    
    env = WebAgentTextEnv(observation_mode="text", human_goals=True)
    files = os.listdir(trial_log_dir)
    model = AnyOpenAILLM(model_name=model_name, model_kwargs={"temperature": 0.0})
    existing_interactions = []
    if files:
        existing_interactions = [f for f in files if f.endswith('.json')]
        print('existing num', len(existing_interactions))

    path = {}
    for z, env_config in enumerate(env_configs):
        
        if env_config['is_skip']:
            continue
        if f'{z}.json' in existing_interactions:
            continue

        env.reset(z)
        final_env_history, is_success, reward_info, true_item, is_halted = webshop_run(env, BASE_PROMPT, env_config["memory"], model)

        path['path'] = messages_to_dict(final_env_history.messages)
        path['trace_correct'] = int(is_success)
        path['true_item'] = true_item
        path['reward_info'] = reward_info
        path["is_halted"] = is_halted
        # log env results to trial log
        with open(os.path.join(trial_log_dir, f'{z}.json'), 'w') as wf:
            json.dump(path, wf, indent=4)
