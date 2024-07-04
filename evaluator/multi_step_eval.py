from .base_evaluator import BaseEvaluator
import re
from prompts.webshop_prompt import web_multi_step, web_multi_step_risk_sen
from prompts.hotpotqa_prompt import hotpot_multi_step
from prompts.alfworld_prompt import alfworld_multi_step, alfworld_multi_step_risk_sen
from .utils_eval import (
    get_trajectory_webshop,
    get_trajectory_hotpotqa,
    get_trajectory_alfworld,
    extract_price,
    get_risk_level)
from langchain.schema import HumanMessage

class MultistepEvaluator(BaseEvaluator):
    def __init__(self, task, **kwargs) -> None:
        super().__init__(task, **kwargs)
    
    def evaluate(self, message, compiler=re.compile(r"Step ([0-9]+): ([\d.]+)"), **kwargs):
        if self.task.lower() == "webshop":
            messages, original_task = get_trajectory_webshop(message)

            if kwargs.get("risk_mode", False):
                multi_step_prompt = web_multi_step
            else:
                multi_step_prompt = web_multi_step_risk_sen

        elif self.task.lower() == "hotpotqa":
            messages, original_task = get_trajectory_hotpotqa(message)
            multi_step_prompt = hotpot_multi_step


        elif self.task.lower() == "alfworld":
            messages, original_task = get_trajectory_alfworld(message)
            if kwargs.get("risk_mode", False):
                multi_step_prompt = alfworld_multi_step_risk_sen
            else:
                multi_step_prompt = alfworld_multi_step

        if kwargs['risk_mode']:
            risk_level = get_risk_level(self.task, messages)
            if risk_level != "high_risk":
                return None

        items = {}
        for ix, traj in enumerate(messages):
            trajectory = "\n".join(traj)
            prompt = multi_step_prompt.format(
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
    @classmethod
    def metric(self, json_objects, **kwargs):
        cost = 0
        true_negative, false_positive, false_negative, true_positive = 0, 0, 0, 0
        fn_envs, predictions, y_true, y_pred, tp_tasks = [], [], [], [], []
        for obj in json_objects:
            y_pred.append(0)
            for ix in obj['real-time eval']:
                if obj['real-time eval'][ix]["probs"]:
                    probs = [opt[1] for opt in obj['real-time eval'][ix]["probs"]]
                    final_prob = kwargs['aggregated_func'](probs)
                    y_pred[-1] = 1 - final_prob
                    if final_prob > kwargs['threshold']:
                        pred_label = "Correct"
                    else:
                        pred_label = "Incorrect"
                        break
                else:
                    pred_label = "N/A"
                    break
            if obj["trace_correct"]:
                y_true.append(0)
                if pred_label == "Correct":
                    true_negative += 1
                else:
                    if pred_label == "N/A":
                        y_pred[-1] = 1
                    false_positive += 1
                    predictions.append({"env_name": obj["env_name"], "true_label": "Correct"})
            else:
                y_true.append(1)
                if pred_label == "Incorrect":
                    true_positive += 1
                    predictions.append({"env_name": obj["env_name"], "true_label": "Incorrect"})
                    try:
                        tp_tasks.append(obj["input_task"])
                    except:
                        continue
                else:
                    if pred_label == "N/A":
                        y_pred[-1] = 0
                    if kwargs['task'] == 'webshop':
                        try:
                            cost += float(obj["selected_product_price"][0])
                        except:
                            pass
                    else:
                        cost += 1
                    false_negative += 1
                    fn_envs.append(obj["env_name"])
        return {
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "false_negative_env": fn_envs,
            "y_true": y_true,
            "y_pred": y_pred,
            "fn_envs": fn_envs,
            "fn_cost": cost
        }, tp_tasks, predictions