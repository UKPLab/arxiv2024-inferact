import re
from langchain.memory import ChatMessageHistory
from langchain.schema import HumanMessage, AIMessage
from llm import AnyOpenAILLM, LocalLLM
from typing import Dict, List
import os
import json
from datetime import datetime
import argparse
from tqdm import tqdm
from prompts.webshop_prompt import (
    web_k_task_inference_prompt,
    web_self_eval_prompt_template,
    web_multi_step_confidence,
    web_task_validator_prob_prompt,
    web_self_eval_risk_sen_prompt_template,
    web_multi_step_confidence_risk_sen,
    web_task_validator_risk_sen_prob_prompt,
)
from prompts.hotpotqa_prompt import (
    hotpot_k_task_inference_prompt,
    hotpot_self_eval_prompt_template,
    hotpot_task_validator_prob_prompt,
    hotpot_multi_step_confidence,
)

from prompts.alfworld_prompt import (
    alfworld_k_task_inference_prompt,
    alfworld_self_eval_prompt_template,
    alfworld_multi_step_confidence,
    alfworld_task_validator_prob_prompt,
    alfworld_self_eval_prompt_template_risk_sen,
    alfworld_task_validator_prob_prompt_risk_sen,
    alfworld_multi_step_confidence_risk_sen,
)

from utils_eval import (
    get_trajectory_webshop,
    get_trajectory_hotpotqa,
    get_action_chain_webshop,
    get_action_chain_hotpotqa,
    get_trajectory_alfworld,
    get_action_chain_alfworld,
    extract_price,
    get_inferred_tasks,
    convert_json_objs
)



class Evaluator:
    def __init__(self, task, **kwargs) -> None:
        if "gpt" in kwargs["model_name"]:
            self.base_model = AnyOpenAILLM(
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_new_tokens", 500),
                model_name=kwargs.get("model_name", "gpt4-turbo-128k"),
            )
        elif "llama" in kwargs["model_name"]:
            self.base_model = LocalLLM(
                model_pth=kwargs["model_path"],
                tokenizer_pth=kwargs["model_path"],
                max_new_tokens=kwargs.get("max_new_tokens", 500),
            )

        self.task = task
        self.label_map = {
            1: "A",
            2: "B",
            3: "C",
            4: "D",
            5: "E"
        }
        if task == 'alfworld':
            self.reverse_mapping = self.generate_mapping(4)
        else:
            self.reverse_mapping = self.generate_mapping(5)

    def task_inference(self, seq_actions, model_name, num_tasks="three"):
        k_task_inference = k_task_inference_prompt.format(
            action=seq_actions, num_tasks=num_tasks
        )
        if self.task == "WebShop":
            split_phrase = f"The {num_tasks} most likely user's instructions are:"
        elif self.task == "hotpotqa":
            split_phrase = f"The {num_tasks} most likely questions are:"
        elif self.task == "alfworld":
            split_phrase = f"The {num_tasks} most likely tasks are:"

        inferred_tasks = self.base_model([HumanMessage(content=k_task_inference)])
        try:
            splitted = inferred_tasks.split("The reason is")
            inferred_tasks = splitted[0].split(split_phrase)[1].strip().split("\n")
            # the inferred tasks: A. task1\nB. task2\nC. task3\n
            inferred_tasks_dic = {
                q.split(".", 1)[0].strip(): q.split(".", 1)[1].strip()
                for q in inferred_tasks
                if q.strip()
            }
            reason = splitted[1].strip()
        except:
            inferred_tasks_dic = {}
            reason = ""
        return inferred_tasks_dic, reason

    def self_eval(self, message, **kwargs):
        if self.task.lower() == "webshop":
            messages, original_task = get_trajectory_webshop(message)

        elif self.task.lower() == "hotpotqa":
            messages, original_task = get_trajectory_hotpotqa(message)

        elif self.task.lower() == "alfworld":
            # alfworld exists critical actions in the middle
            messages, original_task = get_trajectory_alfworld(message)

        if args.task == "alfworld":
            compiler = re.compile(r"(\w+): ([^\n]+)")

        alert_trajectory_ix = -1
        items = {}
        for ix, traj in enumerate(messages):

            trajectory = "\n".join(traj)
            prompt = self_eval_prompt_template.format(
                trajectory=trajectory, instruction=original_task
            )
            # print('prompt', prompt)
            try:
                result = self.base_model([HumanMessage(content=prompt)])
                if args.task != "alfworld":
                    splitted = result.split("Confidence:")
                    yes_no = splitted[0].split("The answer is:")[1].strip()
                    confidence = splitted[1].split("Justification:")[0].strip()
                    justification = splitted[1].split("Justification:")[1].strip()
                    completion = "Completed"
                else:
                    # try:
                    matches = compiler.findall(result)
                    completion = matches[0][1]
                    yes_no = matches[1][1]
                    confidence = matches[2][1]
                    justification = matches[3][1]
                    # except:
                        # ipdb.set_trace()

                items[ix] = {
                    "yes_no": yes_no,
                    "confidence": confidence,
                    "justification": justification,
                    "completion": completion,
                    "input_messages": traj,
                    "alert_ix": alert_trajectory_ix,
                }

                if yes_no == "Incorrect":
                    alert_trajectory_ix = ix
                    break
            except Exception as e:
                print(e)
                items[ix] = {
                    "yes_no": "N/A",
                    "confidence": "N/A",
                    "justification": "N/A",
                    "completion": "N/A",
                    "input_messages": traj,
                    "alert_ix": alert_trajectory_ix,
                }
        if self.task == "WebShop":
            return {
                "real-time eval": items,
                "complete_traj": messages,
                "input_task": original_task,
                "env_name": kwargs["env_name"],
                "selected_product_price": extract_price(messages[0]),
            }
        else:
            return {
                "real-time eval": items,
                "complete_traj": messages,
                "input_task": original_task,
                "env_name": kwargs["env_name"],
            }


    def self_consistency(self, message, m=5, **kwargs):

        if self.task.lower() == "webshop":
            messages, original_task = get_trajectory_webshop(message)

        elif self.task.lower() == "hotpotqa":
            messages, original_task = get_trajectory_hotpotqa(message)

        elif self.task.lower() == "alfworld":
            # alfworld exists critical actions in the middle
            messages, original_task = get_trajectory_alfworld(message)

        if args.task == "alfworld":
            compiler = re.compile(r"(\w+): ([^\n]+)")

        alert_trajectory_ix = -1
        ensemble = {}
        for ix, traj in enumerate(messages):
            trajectory = "\n".join(traj)
            prompt = self_eval_prompt_template.format(
                trajectory=trajectory, instruction=original_task
            )
            ensemble[ix] = {}
            try:
                for _ in range(m):
                    result = self.base_model([HumanMessage(content=prompt)])
                    if args.task != "alfworld":
                        splitted = result.split("Confidence:")
                        yes_no = splitted[0].split("The answer is:")[1].strip()
                        confidence = splitted[1].split("Justification:")[0].strip()
                        justification = splitted[1].split("Justification:")[1].strip()
                        completion = "Completed"
                    else:
                        matches = compiler.findall(result)
                        completion = matches[0][1]
                        yes_no = matches[1][1]
                        confidence = matches[2][1]
                        justification = matches[3][1]

                    # items[ix] = {
                    #         "yes_no": yes_no,
                    #         "confidence": confidence,
                    #         "justification": justification,
                    #         "completion": completion,
                    #         "input_messages": traj,
                    #         "input_task": original_task,
                    #         "alert_ix": alert_trajectory_ix}
                    ensemble[ix]["yes_no"] = ensemble[ix].get("yes_no", []) + [yes_no]
                    ensemble[ix]["completion"] = ensemble[ix].get("completion", []) + [
                        completion
                    ]
                    ensemble[ix]["confidence"] = ensemble[ix].get("confidence", []) + [
                        float(confidence)
                    ]
                    ensemble[ix]["justification"] = ensemble[ix].get(
                        "justification", []
                    ) + [justification]
                ensemble[ix]["alert_ix"] = alert_trajectory_ix
                ensemble[ix]["input_messages"] = traj
                yes_no = max(
                    set(ensemble[ix]["yes_no"]), key=ensemble[ix]["yes_no"].count
                )
                confidence = sum(ensemble[ix]["confidence"]) / len(
                    ensemble[ix]["confidence"]
                )
                ensemble[ix]["final_yes_no"] = yes_no
                ensemble[ix]["final_confidence"] = confidence
            except:

                ensemble[ix]["final_yes_no"] = "N/A"
                ensemble[ix]["final_confidence"] = "N/A"
                ensemble[ix]["alert_ix"] = alert_trajectory_ix
                ensemble[ix]["input_messages"] = traj
                ensemble[ix]["justification"] = "N/A"
                ensemble[ix]["completion"] = "N/A"
                ensemble[ix]["yes_no"] = "N/A"
                ensemble[ix]["confidence"] = "N/A"
                ensemble[ix]["alert_ix"] = alert_trajectory_ix
                ensemble[ix]["input_messages"] = traj

            if (
                ensemble[ix]["final_yes_no"] == "Incorrect"
                or ensemble[ix]["final_yes_no"] == "N/A"
            ):
                alert_trajectory_ix = ix
                break
        if self.task == "WebShop":
            return {
                "real-time eval": ensemble,
                "complete_traj": messages,
                "input_task": original_task,
                "env_name": kwargs["env_name"],
                "selected_product_price": extract_price(messages[0]),
            }
        else:
            return {
                "real-time eval": ensemble,
                "complete_traj": messages,
                "input_task": original_task,
                "env_name": kwargs["env_name"],
            }

    def multi_step(
        self, message, compiler=re.compile(r"Step ([0-9]+): ([\d.]+)"), **kwargs
    ):
        if self.task.lower() == "webshop":
            messages, original_task = get_trajectory_webshop(message)

        elif self.task.lower() == "hotpotqa":
            messages, original_task = get_trajectory_hotpotqa(message)

        elif self.task.lower() == "alfworld":
            messages, original_task = get_trajectory_alfworld(message)

        items = {}
        for ix, traj in enumerate(messages):
            trajectory = "\n".join(traj)
            prompt = multi_step_confidence.format(
                instruction=original_task, trajectory=trajectory
            )
            result = self.base_model([HumanMessage(content=prompt)])
            try:
                splitted = result.split("Justification:")
                matches = compiler.findall(splitted[0])
                probs = [(g, float(p)) for g, p in matches]
                justifcation = splitted[1]
            except:
                # ipdb.set_trace()
                probs = []
                justifcation = result
            items[ix] = {
                "probs": probs,
                "justification": justifcation,
                "input_messages": traj,
            }
        if self.task == "WebShop":
            return {
                "real-time eval": items,
                "complete_traj": messages,
                "input_task": original_task,
                "env_name": kwargs["env_name"],
                "selected_product_price": extract_price(messages[0]),
            }
        else:
            return {
                "real-time eval": items,
                "complete_traj": messages,
                "input_task": original_task,
                "env_name": kwargs["env_name"],
            }

    def inferact(self, message, model_name, **kwargs):
        if self.task.lower() == "webshop":
            action_chain, original_task = get_action_chain_webshop(message)
        elif self.task.lower() == "hotpotqa":
            action_chain, original_task = get_action_chain_hotpotqa(message)

        elif self.task.lower() == "alfworld":
            action_chain, original_task = get_action_chain_alfworld(message)

        results = {}
        for ix, chain in enumerate(action_chain):
            chain_str = "\n".join(chain)
            if "inferred_tasks" not in kwargs:
                try:
                    inferred_tasks_dic, inferred_tasks_reason = self.task_inference(
                        chain_str, model_name
                    )
                except:
                    ipdb.set_trace()
                    results[ix] = {
                        "candidates": "N/A",
                        "candidates_reverse": "N/A",
                        "answer_justification": "N/A",
                        "answer_justification_reverse": "N/A",
                        "inferred_tasks_reason": "N/A",
                        "tasks_string": "N/A",
                        "task_string_reverse": "N/A",
                        "gold_option": "N/A",
                        "aggregated_probs": "N/A",
                        "input_messages": chain,
                    }
                    continue

                tasks = list(inferred_tasks_dic.values())
                tasks.append(original_task)
                if self.task != "alfworld":
                    tasks.append("None of the above")

                tasks_string = "\n".join(
                    [
                        f"{self.label_map[ix+1]}. {q.strip()}"
                        for ix, q in enumerate(tasks)
                    ]
                )
                task_string_reverse = "\n".join(
                    [
                        f"{self.label_map[ix+1]}. {q.strip()}"
                        for ix, q in enumerate(tasks[::-1])
                    ]
                )
            else:
                tasks_string, task_string_reverse = kwargs["inferred_tasks"]
                tasks = tasks_string.split("\n")
                inferred_tasks_reason = "N/A"
            # if len(tasks) != 4:
            #     print('length of tasks is not 4')
            if "None of the above" in tasks[-1]:
                gold_label = self.label_map[len(tasks) - 1]
            else:
                gold_label = self.label_map[len(tasks)]

            validator_prompt = task_validator_prob_prompt
            # elif model_name == "gpt-35-turbo-0613-16k":
            #     validator_prompt = task_validator_prob_prompt_35

            task_validator = validator_prompt.format(
                action=chain_str, instructions=tasks_string, num=len(tasks)
            )

            task_validator_revserse = validator_prompt.format(
                action=chain_str, instructions=task_string_reverse, num=len(tasks)
            )
            try:
                # maybe order senstitive: swap the instrction1 and instruction2
                result = self.base_model([HumanMessage(content=task_validator)])

                result_reverse = self.base_model(
                    [HumanMessage(content=task_validator_revserse)]
                )

                splitted = result.split("Justification:")
                candidates = splitted[0].strip()
                answer_justification = splitted[1].strip()

                splitted_reverse = result_reverse.split("Justification:")
                candidates_reverse = splitted_reverse[0].strip()
                answer_justification_reverse = splitted_reverse[1].strip()

                # extract probablity and the reason
                if self.task != "alfworld":
                    compiler = re.compile(r"G\d+: ([A-Z])\.? P\d+: (\d+\.\d+)")
                else:
                    compiler = re.compile(r"P\_([A-Z])\: (\d+\.\d+)")
                matches = compiler.findall(candidates)
                candidates = [(g, float(p)) for g, p in matches]

                matches_reverse = re.findall(compiler, candidates_reverse)

                candidates_reverse = [(g, float(p)) for g, p in matches_reverse]
                # evaluate
                # evaluate if the number is correct
                # if self.task != "alfworld":
                #     option_label = ["A", "B", "C", "D", "E", ""]
                # else:
                #     option_label = ["A", "B", "C", "D"]
                # # if not in the candidates, add it into 0.0
                # for option in option_label:
                #     if option not in [c[0] for c in candidates]:
                #         candidates.append((option, 0.0))
                #     if option not in [c[0] for c in candidates_reverse]:
                #         candidates_reverse.append((option, 0.0))

                aggregated_probs = self.aggregate_probability(
                    candidates, candidates_reverse
                )
                results[ix] = {
                    "candidates": candidates,
                    "candidates_reverse": candidates_reverse,
                    "answer_justification": answer_justification,
                    "answer_justification_reverse": answer_justification_reverse,
                    "inferred_tasks_reason": inferred_tasks_reason,
                    "tasks_string": tasks_string,
                    "task_string_reverse": task_string_reverse,
                    "gold_option": gold_label,
                    "aggregated_probs": aggregated_probs,
                    "input_messages": chain,
                }
            except:
                # ipdb.set_trace()
                results[ix] = {
                    "candidates": result,
                    "candidates_reverse": result_reverse,
                    "answer_justification": "N/A",
                    "answer_justification_reverse": "N/A",
                    "inferred_tasks_reason": "N/A",
                    "tasks_string": tasks_string,
                    "task_string_reverse": task_string_reverse,
                    "gold_option": gold_label,
                    "aggregated_probs": "N/A",
                    "input_messages": chain,
                }
        if self.task == "WebShop":
            return {
                "real-time eval": results,
                "input_task": original_task,
                "env_name": kwargs.get("env_name", ""),
                "selected_product_price": extract_price(action_chain[0]),
            }
        else:
            return {
                "real-time eval": results,
                "input_task": original_task,
                "env_name": kwargs.get("env_name", ""),
            }


    def generate_mapping(self, n):
        # Generate a list of options
        options = list('ABCDE'[:n])
        
        # Generate the mapping
        mapping = {options[i]: options[-(i+1)] for i in range(n)}
        
        return mapping

    def aggregate_probability(self, probs, probs_reverse):
        # align the option order between reversed and original
        option2prob = {option[0]: option[1] for option in probs}
        for reversed_option in probs_reverse:
            # order = self.label_map[len(probs) + 1 - self.alp2ix[reversed_option[0]]]
            order = self.reverse_mapping[reversed_option[0]]
            option2prob[order] = (option2prob.get(order, 0) + reversed_option[1]) / 2

        # sort the option by probability
        sorted_option = sorted(option2prob.items(), key=lambda x: x[1], reverse=True)
        return sorted_option


if __name__ == "__main__":
    # add argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="gpt4-turbo-128k")
    parser.add_argument("--model_path", type=str, default="", help="path to the local model")
    parser.add_argument(
        "--save_dir",
        type=str,
        default="/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results",
    )
    parser.add_argument(
        "--eval_method", type=str, default="self_eval", help="self_eval, wiseacquire"
    )
    parser.add_argument("--subset", type=str, default="200-300")
    parser.add_argument(
        "--add_justification", action="store_true", help="Add justification"
    )
    parser.add_argument("--task", type=str, default="", required=True)
    parser.add_argument("--trial_num", type=int, default=0)
    parser.add_argument("--risk_mode", action="store_true", help="sensitive mode")
    parser.add_argument("--signature", type=str, default="")
    parser.add_argument("--threshold", type=str, default="")
    parser.add_argument("--traj_dir", type=str, default="/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/actor-traj")

    args = parser.parse_args()

    kwargs_init = {"model_path": args.model_path, "model_name": args.model_name}

    if args.eval_method == "self_consistency":
        kwargs_init["temperature"] = 0.7

    evaluator = Evaluator(task=args.task, **kwargs_init)
    root_dir = "/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/actor-traj"
    if args.trial_num > 0:
        actor_flies_dir = (
            f"{root_dir}/{args.task}/retrial_{args.trial_num}/{args.subset}"
        )
    else:
        actor_flies_dir = f"{root_dir}/{args.task}/retrial_0/{args.subset}"

    if args.model_name == "gpt4-turbo-128k":
        save_dir = args.save_dir + "/gpt4-turbo"

    elif args.model_name == "gpt-35-turbo-0613-16k":
        # dir_path = f"{args.save_dir}/gpt35-turbo/{args.task}/{args.subset}"
        save_dir = args.save_dir + "/gpt35-turbo"
    elif args.model_name == "llama-3-70B":
        save_dir = args.save_dir + "/llama-3-70B"

    # filter trajectory for different methods
    if args.trial_num > 0:
        files = []
        last_rejected_path = os.path.join(
            save_dir,
            f"{args.task}_eval_metrics",
            args.eval_method,
            f"retrial_{args.trial_num-1}",
            "" if args.trial_num == 1 else args.subset,
            f"predicted_pos{args.threshold}.json",
        )
        # print('args.threshold', args.threshold)
        with open(last_rejected_path, 'r') as f:
            last_rejected = json.load(f)
        if args.eval_method == "multi_step":
            last_rejected = last_rejected['prod']
        for f in last_rejected:
            if f['true_label'] == 'Incorrect':
                files.append(f['env_name'])
                # if f['folder_name'] in ['NL.txt', 'binary.txt']:
                #     files.append(f['env_name'])
                # else:
                #     files.append(f['env_name']+f"_{f['folder_name'].replace('txt','json')}")

        # last_halt_dir = os.path.join(
        #     "/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/actor-traj",
        #     f"{args.task}",
        #     f"retrial_{args.trial_num-1}")
        # subfolder = os.listdir(last_halt_dir)

        # if args.trial_num == 1:
        #     for folder in subfolder:
        #         items = os.listdir(os.path.join(last_halt_dir, folder))

                  
        #             files.append(item)
        # else:
        #     subfiles = os.listdir(os.path.join(last_halt_dir, args.subset))
        #     for f in subfiles:
        #         # print(os.path.join(last_halt_dir, args.subset, f))
        #         with open(os.path.join(last_halt_dir, args.subset, f), "r") as f:
        #             data = json.load(f)
        #         if data.get('halt', False):
        #             files.append(f)

    else:
        actor_flies_dir = '/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/actor-traj/WebShop/human_feedback/retrial_2/NL'
        files = os.listdir(actor_flies_dir)
        files = sorted(files)
        # wiseacquire for gpt35, llama-3
        # files = ['130', '115', '117', '126']
        #self_consistency, self_eval for gpt35, llama-3
        # files = ['130', '115', '126']


    if args.task == "WebShop":
        k_task_inference_prompt = web_k_task_inference_prompt
        if args.risk_mode:
            self_eval_prompt_template = web_self_eval_risk_sen_prompt_template
            multi_step_confidence = web_multi_step_confidence_risk_sen
            task_validator_prob_prompt = web_task_validator_risk_sen_prob_prompt
        else:
            self_eval_prompt_template = web_self_eval_prompt_template
            multi_step_confidence = web_multi_step_confidence
            task_validator_prob_prompt = web_task_validator_prob_prompt
        with open("/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/actor-traj/WebShop/halted_files.json", "r") as f:
            halted_files = json.load(f)
        

        # task_validator_prob_prompt_35 = web_task_validator_prob_prompt_35

    elif args.task == "hotpotqa":
        k_task_inference_prompt = hotpot_k_task_inference_prompt
        self_eval_prompt_template = hotpot_self_eval_prompt_template
        multi_step_confidence = hotpot_multi_step_confidence
        task_validator_prob_prompt = hotpot_task_validator_prob_prompt

    elif args.task == "alfworld":
        k_task_inference_prompt = alfworld_k_task_inference_prompt
        if args.risk_mode:
            self_eval_prompt_template = alfworld_self_eval_prompt_template_risk_sen
            multi_step_confidence = alfworld_multi_step_confidence_risk_sen
            task_validator_prob_prompt = alfworld_task_validator_prob_prompt_risk_sen
        else:
            self_eval_prompt_template = alfworld_self_eval_prompt_template
            multi_step_confidence = alfworld_multi_step_confidence
            task_validator_prob_prompt = alfworld_task_validator_prob_prompt

    if args.risk_mode:
        eval_result_dir = os.path.join(
            save_dir, args.task, args.eval_method, f"retrial_{args.trial_num}_sensitive"
        )
    else:
        if args.trial_num == 0:
            eval_result_dir = os.path.join(
                save_dir,
                args.task,
                args.eval_method,
                args.signature,
                f"retrial_0",
            )
        else:
            eval_result_dir = os.path.join(
                save_dir,
                args.task,
                args.eval_method,
                args.signature,
                f"retrial_{args.trial_num}",
                args.subset
            )


    if not os.path.exists(eval_result_dir):
        os.makedirs(eval_result_dir)

    kwargs = {"risk_mode": args.risk_mode}
    if args.eval_method == "wiseacquire":
        kwargs.update({"model_name": args.model_name})
        if args.risk_mode:
            env2inferred_tasks = get_inferred_tasks(
                f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/gpt4-turbo/{args.task}/wiseacquire/retrial_0/{args.subset}.txt"
            )
    # load existing data
    existing_envs = []
    if os.path.exists(os.path.join(eval_result_dir, f"{args.subset}.txt")):
        entries = convert_json_objs(os.path.join(eval_result_dir, f"{args.subset}.txt"))
        existing_envs = [entry["env_name"] + '.json' for entry in entries]

    f_file = open(
        os.path.join(eval_result_dir, f"{args.subset}.txt"),
        "a",
    )

    f_cost = open("./total_cost.txt", "a")
    correct = 0
    total = 0

    if args.risk_mode:
        if args.task == "WebShop":
            files = [
                "49",
                "72",
                "19",
                "13",
                "58",
                "90",
                "111",
                "145",
                "188",
                "222",
                "205",
                "212",
                "213",
                "217",
                "226",
                "236",
                "247",
                "261",
                "277",
                "37",
                "9",
                "38",
                "4",
                "40",
                "5",
                "56",
                "62",
                "74",
                "103",
                "133",
                "139",
                "162",
                "173",
                "182",
                "106",
                "116",
                "117",
                "124",
                "134",
                "144",
                "148",
                "172",
                "176",
                "187",
                "191",
                "230",
                "246",
                "260",
                "264",
                "267",
                "209",
                "211",
                "233",
                "235",
                "245",
                "251",
                "258",
                "266",
                "272",
                "287",
                "289",
                "291",
                "293",
            ]
        elif args.task == "alfworld":
            files = [
                "11",
                "14",
                "23",
                "24",
                "31",
                "33",
                "41",
                "47",
                "55",
                "57",
                "60",
                "62",
                "64",
                "67",
                "73",
                "86",
                "89",
                "91",
                "94",
                "99",
                "1",
                "2",
                "20",
                "35",
                "54",
                "68",
                "70",
                "76",
                "82",
                "83",
                "85",
                "96",
                "101",
                "108",
                "112",
                "132",
                "105",
                "110",
                "113",
                "114",
                "122",
                "123",
                "124"]
    
    for ix, file in tqdm(enumerate(files)):
        if not file.endswith(".json"):
            file = file + ".json"
        if file in existing_envs:
            print(f"{file} is already evaluated")
            continue
        kwargs["env_name"] = file.split(".")[0]
        if args.eval_method == "wiseacquire" and args.risk_mode:
            try:
                kwargs["inferred_tasks"] = env2inferred_tasks[kwargs["env_name"]]
            except:
                print(f"there is no {kwargs['env_name']} in the inferred tasks")
                pass

        if "config" in file:
            continue
        if not os.path.exists(os.path.join(actor_flies_dir, file)):
            print(f"there is no {os.path.join(actor_flies_dir, file)}")
            continue
        with open(os.path.join(actor_flies_dir, file), "r") as f:
            data = json.load(f)
        if type(data) == list:
            data = data[0]
            with open(os.path.join(actor_flies_dir, file), "w") as f:
                json.dump(data, f)

        is_halted = data.get("is_halted", False)
        if is_halted:
            print(f"{file} is halted")
            continue
        message = data["path"]

        eval_method = getattr(evaluator, args.eval_method)
        output = eval_method(message, **kwargs)
        if not output:
            continue
        # add into a json object
        output["trace_correct"] = data["trace_correct"]
        if args.task == "WebShop":
            output["true_item"] = data["true_item"]

        f_file.write(json.dumps(output, indent=4) + "\n")
        f_file.flush()
        # candidates_reverse = [evaluator.label_map[5 - evaluator.alp2ix[candid]] for candid in candidates_reverse]
        # if gold_label not in candidates and gold_label not in candidates_reverse:
        #     correct += 1
        # total += 1
        if "gpt" in args.model_name:
            f_cost.write(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},{evaluator.base_model.total_cost}\n"
            )

        evaluator.base_model.total_cost = 0
        f_cost.flush()

    f_file.close()
    f_cost.close()
