from .base_evaluator import BaseEvaluator
from llm import AnyOpenAILLM, LocalLLM
from .utils_eval import (
    get_trajectory_webshop,
    get_trajectory_hotpotqa,
    get_trajectory_alfworld,
    extract_price,
    get_risk_level)
import re
from langchain.schema import HumanMessage
from prompts.webshop_prompt import web_standard_eval, web_standard_eval_risk_sen
from prompts.alfworld_prompt import alfworld_standard_eval, alfworld_standard_eval_risk_sen
from prompts.hotpotqa_prompt import hotpot_standard_eval


class StandardEvaluatorSC(BaseEvaluator):
    def __init__(self, task, **kwargs) -> None:
        super().__init__(task, **kwargs)
    
    def evaluate(self,  message, m=5, **kwargs):
        if self.task == "webshop":
            messages, original_task = get_trajectory_webshop(message)

            if kwargs.get("risk_mode", False):
                self_eval_prompt_template = web_standard_eval_risk_sen
            else:
                self_eval_prompt_template = web_standard_eval

        elif self.task == "hotpotqa":
            messages, original_task = get_trajectory_hotpotqa(message)
            self_eval_prompt_template = hotpot_standard_eval

        elif self.task == "alfworld":
            # alfworld exists critical actions in the middle
            messages, original_task = get_trajectory_alfworld(message)
            
            if kwargs.get("risk_mode", False):
                self_eval_prompt_template = alfworld_standard_eval_risk_sen
            else:
                self_eval_prompt_template = alfworld_standard_eval

        if kwargs['risk_mode']:
            risk_level = get_risk_level(self.task, messages)
            if risk_level != "high_risk":
                return None

        if self.task == "alfworld":
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
                    if self.task != "alfworld":
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
        
    @classmethod
    def metric(self, json_objects, **kwargs):
        true_positive, true_negative, false_positive, false_negative = 0, 0, 0, 0
        tp_tasks, predictions = [], []
        fn_envs, y_true = [], []
        pred_label_key = "final_yes_no"
        cost = 0.0
        for obj in json_objects:
            pred_label = "Correct"
            for ix in obj["real-time eval"]:
                if obj["real-time eval"][ix][pred_label_key] == "N/A":
                    pred_label = "N/A"
                    break
                if obj["real-time eval"][ix][pred_label_key] == "Incorrect":
                    pred_label = "Incorrect"
                    break

            if obj["trace_correct"]:
                y_true.append(0.0)
                if pred_label == "Correct":
                    true_negative += 1
                else:
                    false_positive += 1
                    try:
                        predictions.append({"env_name": obj["env_name"], "true_label": "Correct"})
                    except Exception as e:
                        print(e)
                        pass
            else:
                y_true.append(1.0)
                if pred_label == "Incorrect":
                    true_positive += 1
                    try:
                        predictions.append({"env_name": obj["env_name"], "true_label": "Incorrect"})
                        tp_tasks.append(obj['input_task'])
                    except:
                        pass
                
                else:
                    if kwargs['task'] == 'webshop':
                        try:
                            cost += float(obj["selected_product_price"][0])
                        except:
                            # some trajs don't have selected_product_price
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
            "y_true": y_true,
            "y_pred": [],
            "false_negative_env": fn_envs,
            "fn_cost": cost            
        }, tp_tasks, predictions
