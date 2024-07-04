import tiktoken
from copy import deepcopy
import os
gpt2_enc = tiktoken.encoding_for_model("text-davinci-003")
import json
import ipdb
import re

def get_trajectory_webshop(message):
    message = message[10:]
    messages = []
    for ix, msg in enumerate(message):
        if msg["type"] == "human":
            msg = msg["data"]["content"]
            if not msg.startswith("Observation"):
                messages.append("Observation:\n" + msg)
            else:
                messages.append(msg)
        elif msg["type"] == "ai":
            msg = msg["data"]["content"]
            messages.append(msg)
    # remove the last one if it is the result of buy now
    if "click[Buy Now]" in messages[-2]:
        messages = messages[:-1]
    original_task = message[0]["data"]["content"].split("[SEP]")[2].strip()
    return [messages], original_task

def get_trajectory_hotpotqa(message):
    messages = []
    for msg in message:
        if msg["type"] == "human":
            assert msg["data"]["content"].startswith("Question: ")
            original_task = msg["data"]["content"].replace("Question: ", "").strip()
        elif msg["type"] == "ai":
            messages.append(msg["data"]["content"])
    return [messages], original_task


def get_trajectory_alfworld(message):
    original_task = message[0]["data"]["content"].split("\n")[-1]
    assert original_task.startswith("Your task is to:")
    original_task = original_task.replace("Your task is to:", "").strip()
    complete_trajectory = []
    partial_trajectories = []
    critical_actions = ["> clean", "> heat", "> cool"]
    for msg in message[1:]:
        complete_trajectory.append(msg["data"]["content"])
        if msg["type"] == "ai":
            for action in critical_actions:
                if action in msg["data"]["content"].lower():
                    partial_trajectories.append(deepcopy(complete_trajectory))

    partial_trajectories.append(complete_trajectory)
    return partial_trajectories, original_task
        
def get_action_chain_alfworld(message):
    original_task = message[0]["data"]["content"].split("\n")[-1]
    assert original_task.startswith("Your task is to:")
    original_task = original_task.replace("Your task is to:", "").strip()
    critical_actions = ["> clean", "> heat", "> cool"]
    complete_action_chain, partial_action_chains = [], []
    skip_next = False
    for msg in message[1:]:
        if skip_next:
            skip_next = False
            continue
        if msg["type"] == "ai":
            if "> think:" in msg["data"]["content"]: 
                skip_next = True
                continue
            complete_action_chain.append(msg["data"]["content"])
            for action in critical_actions:
                if action in msg["data"]["content"].lower():
                    partial_action_chains.append(deepcopy(complete_action_chain))

        elif msg["type"] == "human":
            complete_action_chain.append(msg["data"]["content"])
    partial_action_chains.append(complete_action_chain)

    return partial_action_chains, original_task

def get_action_chain_webshop(message, mask_search=True, keep_thought=False):
    message = message[10:]
    action_chain = []
    for ix, msg in enumerate(message):
        if msg["type"] == "ai":
            action = msg["data"]["content"].split("Action:")[1].strip()
            if "click[Buy Now]" in action and keep_thought:
                action = msg["data"]["content"]
            if "search" in action and mask_search:
                action = "search"
            action_chain.append("Action:\n" + action)
            obs = message[ix + 1]["data"]["content"].strip()
            obs = "[SEP]".join(obs.split("[SEP]")[2:])
            action_chain.append("Observation:\n" + obs)

    if "click[Buy Now]" in action_chain[-2]:
        action_chain = action_chain[:-1]
    # action_chain.append("Action:\n" + "cllick[Buy Now]")
    original_task = message[0]["data"]["content"].split("[SEP]")[2].strip()
    return [action_chain], original_task

def get_action_chain_hotpotqa(message, tokenizer=gpt2_enc, n_tokens = 2048):

    msg = message[-1]
    assert msg["type"] == "ai"
    scratchpad = msg["data"]["content"]
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
    return [actions_obs], message[0]["data"]["content"].replace("Question: ", "").strip()

def convert_json_objs(file):
    json_objects = []
    buffer = ""
    with open(file, "r") as f:
        for line in f:
            buffer += line
            try:
                json_object = json.loads(buffer)
                json_objects.append(json_object)
                buffer = (
                    ""  # Clear the buffer once we've successfully parsed a JSON object
                )
            except json.JSONDecodeError:
                # If we get a JSONDecodeError, it means that the buffer doesn't contain a complete JSON object
                # So we just continue reading lines into the buffer
                continue
    return json_objects

def get_env_name_for_critic(critic_file, actor_dir, task, method):
    actor_files = os.listdir(actor_dir)
    # inst2env_name
    inst2env_name = {}
    for file in actor_files:
        if not file.endswith(".json"): continue
        with open(os.path.join(actor_dir, file), "r") as f:
            data = json.load(f)
        if task == 'WebShop':
            inst = data["true_item"]['instruction_text']
            # inst = get_trajectory_webshop(data["path"])[0][-1]
            # inst = "\n".join(inst)
        elif task == 'hotpotqa':
            # inst = data["path"][0]["data"]["content"].replace("Question: ", "").strip()
            inst = get_trajectory_hotpotqa(data["path"])[0][-1]
            inst = "\n".join(inst)

        elif task == 'alfworld':
            # inst = get_action_chain_alfworld(data["path"])[0][-1]
            inst = get_trajectory_alfworld(data["path"])[0][-1]
            inst = "\n".join(inst)
            # concat
            # inst = "\n".join([item for sublist in inst for item in sublist])
        inst2env_name[inst] = file.split(".")[0]
    
    data = convert_json_objs(critic_file)
    for entry in data:
        if task == 'alfworld' or task == 'hotpotqa':
            # inst = []
            # inst = "\n".join(entry['complete_traj'][-1])
            key = list(entry['real-time eval'].keys())[-1]
            inst = "\n".join(entry['real-time eval'][key]["input_messages"])
            # ipdb.set_trace()
        else:
            try:
                if task == 'WebShop':
                    inst = entry["true_item"]['instruction_text']
                else:
                    inst = entry["input_task"]
            except:
                try:
                    if method == 'wiseacquire':
                        inferred_tasks = entry["real-time eval"]["0"]["tasks_string"].split('\n')
                        inferred_tasks_dic = {
                            q.split(".", 1)[0].strip(): q.split(".", 1)[1].strip()
                            for q in inferred_tasks
                            if q.strip()
                        }
                        gold_option = entry["real-time eval"]["0"]["gold_option"]
                        inst = inferred_tasks_dic[gold_option]
                    else:
                        inst = entry["real-time eval"]["0"]["input_task"]
                except:
                    ipdb.set_trace()
        try:
            env_name = inst2env_name[inst]
        except:
            continue
    
        entry["env_name"] = env_name
        if 'input_task' not in entry:
            entry['input_task'] = inst
            
    env_names_list = []
    with open(critic_file, "w") as f:
        for entry in data:
            if 'env_name' not in entry:
                continue
            # if int(entry['env_name']) < 134 and int(entry['env_name']) not in env_names_list:
            f.write(json.dumps(entry, indent=4) + '\n')
            env_names_list.append(int(entry['env_name']))
                
def extract_price(messages):
    # Identify the clicked product's ID
    messages = messages[::-1]
    for message in messages:
        # extract moeny in Price: $27.99 using regex
        if "Price:" in message:
            price = re.findall(r'Price:\s*\$([\d.]+)', message)
            return price
    return None

def get_risk_level(task, chains):
    if task == "WebShop":
        price = extract_price(chains[0])
        if price:
            price = float(price[0])
        # Determine the risk level of the object
        if not price:
            object_risk_level = 'N/A'
        # Determine the risk level of the object
        elif price < 15:
            object_risk_level = 'low_risk'
        elif price < 60:
            object_risk_level = 'median_risk'
        elif price >= 60:
            object_risk_level = 'high_risk'

    elif task == "alfworld":
        for chain in chains:
            if chain[-1].startswith("> cool") or chain[-1].startswith("> heat"):
                object_risk_level = "high_risk"
                break
            elif chain[-1].startswith("> clean"):
                object_risk_level = "median_risk"
                break
            else:
                object_risk_level = "low_risk"
    return object_risk_level