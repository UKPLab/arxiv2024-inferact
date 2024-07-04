import json
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc, average_precision_score
from netcal.metrics import ECE
import numpy as np
import ipdb
import argparse
import os
from utils_eval import get_risk_level

def evaluate_non_prob(json_objects):
    correct, incorrect, total = 0, 0, 0
    for obj in json_objects:
        # Now json_objects list contains all the json objects from the file
        options = obj["candidates"].strip(".").split(",")
        options_reversed = (
            obj["candidates_reverse"].split("\n")[0].strip(".").split(",")
        )
        for opt in options_reversed:
            try:
                if opt != "None" and mapping[opt.strip()] not in options:
                    options.append(mapping[opt])
            except:
                print("opt is", opt)
                continue
        if obj["gold_option"] in options:
            if obj["trace_correct"]:
                incorrect += 1
            else:
                correct += 1
        else:
            if obj["trace_correct"]:
                correct += 1
            else:
                print(options, obj["trace_correct"], obj["tasks_string"])
                print("_____")
                incorrect += 1
        total += 1
    print(correct, incorrect, correct / total, incorrect / total, total)


def self_evaluation(json_objects, task, threshold = 0.0, self_consistency=False, risk_level=None):
    true_positive, true_negative, false_positive, false_negative = 0, 0, 0, 0
    y_true, y_pred = [], []
    tp_tasks, predictions = [], []
    cost = 0
    fn_envs = []
    if self_consistency:
        pred_label_key = "final_yes_no"
        pred_confidence_key = "final_confidence"
    else:
        pred_label_key = "yes_no"
        pred_confidence_key = "confidence"

    for obj in json_objects:
        
        if risk_level:
            object_risk_level = get_risk_level(task, obj)
        # Skip the object if its risk level doesn't match the specified risk level
        if risk_level is not None and object_risk_level != risk_level:
            ipdb.set_trace()
            continue
        pred_label = "Correct"
        # only one for each example not for each step
        y_pred.append(0.0)
        for ix in obj["real-time eval"]:
            if obj["real-time eval"][ix][pred_confidence_key] == "N/A":
                pred_label = "N/A"
                break
            y_pred[-1] = 1 - float(obj["real-time eval"][ix][pred_confidence_key])
            if threshold != 0:
                if float(obj["real-time eval"][ix][pred_confidence_key]) <= threshold:
                    pred_label = "Incorrect"
                    break
                else:
                    ipdb.set_trace()
            else:
                if obj["real-time eval"][ix][pred_label_key] == "Incorrect":
                    pred_label = "Incorrect"
                    break

        if obj["trace_correct"]:
            y_true.append(0.0)
            if pred_label == "Correct":
                true_negative += 1
            else:
                if pred_label == "N/A":
                    y_pred[-1] = 1.0
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
                if pred_label == "N/A":
                    y_pred[-1] = 0.0
                if task == 'WebShop':
                    try:
                        cost += float(obj["selected_product_price"][0])
                    except:
                        # some trajs don't have selected_product_price
                        pass
                else:
                    cost += 1
                false_negative += 1
                fn_envs.append(obj["env_name"])
    print('cost', cost)

    return {
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "y_true": y_true,
        "y_pred": y_pred,
        "false_negative_env": fn_envs
    }, tp_tasks, predictions

def self_evaluation_soft(json_objects):
    true_positive, true_negative, false_positive, false_negative = 0, 0, 0, 0
    threshold = 0.5
    y_true, y_pred = [], []
    for obj in json_objects:
        prob = float(obj["prob"])
        if obj["trace_correct"]:
            y_true.append(0)
            y_pred.append(1.0 - prob)
            if prob >= threshold:
                true_negative += 1
            else:
                false_positive += 1
        else:
            y_true.append(1)
            y_pred.append(1.0 - prob)
            if prob < threshold:
                true_positive += 1
            else:
                false_negative += 1

    # ipdb.set_trace()
    # print(roc_auc_score(y_true, y_pred))
    return {
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "y_true": y_true,
        "y_pred": y_pred,
    }

def evaluate_prob_multiclass(json_objects, task, threshold=0.8, risk_level=None):
    y_true, y_pred = [], []
    tp_tasks, predictions = [], []
    env_neg, env_pos = [], []
    fn_envs = []
    true_positive, true_negative, false_positive, false_negative = 0, 0, 0, 0
    cost = 0
    for obj in json_objects:

        if risk_level:
            object_risk_level = get_risk_level(task, obj)
        # Skip the object if its risk level doesn't match the specified risk level
        if risk_level is not None and object_risk_level != risk_level:
            continue
        y_pred.append(0)
        for ix in obj['real-time eval']:
            if obj['real-time eval'][ix]["aggregated_probs"] == "N/A":
                pred_label = "N/A"
                break

            aggregated_probs = {opt[0]: opt[1] for opt in obj['real-time eval'][ix]["aggregated_probs"]}
            try:
                gold_option_prob = aggregated_probs.get(obj['real-time eval'][ix]["gold_option"], 0)
                pos_prob = round(1 - gold_option_prob, 3)
            except:
                ipdb.set_trace()
            y_pred[-1] = pos_prob
            if gold_option_prob > threshold:
                pred_label = "Correct"
            else:
                pred_label = "Incorrect"
                break

        if obj["trace_correct"]:
            y_true.append(0)
            env_neg.append(obj["env_name"])
            if pred_label == "Correct":
                true_negative += 1
            else:
                # ipdb.set_trace()
                false_positive += 1
                predictions.append({"env_name": obj["env_name"], "true_label": "Correct"})
            
        else:
            y_true.append(1)
            env_pos.append(obj["env_name"])
            if pred_label == "Incorrect":
                true_positive += 1
                predictions.append({"env_name": obj["env_name"], "true_label": "Incorrect"})
                try:
                    tp_tasks.append(obj["input_task"])
                except:
                    continue
            else:
                fn_envs.append(obj["env_name"])
                if task == 'WebShop':
                    try:
                        cost += float(obj["selected_product_price"][0])
                    except:
                        pass
                else:
                    cost += 1
                false_negative += 1
    print('cost', cost)


    return {
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "y_true": y_true,
        "y_pred": y_pred,
        "false_negative_env": fn_envs,
    }, tp_tasks, predictions

def evaluate_prob_multiclass_ensemble(json_objects, json_objects2, task, threshold=0.8, risk_level=None):
    # convert json_objects2 to envname2prediction
    env2prediction = {}
    for obj in json_objects2:
        # ipdb.set_trace()
        if "env_name" not in obj:
            continue
        env2prediction[obj["env_name"]] = obj

    y_true, y_pred = [], []
    tp_tasks, predictions = [], []
    env_neg, env_pos = [], []
    true_positive, true_negative, false_positive, false_negative = 0, 0, 0, 0
    for obj in json_objects:

        if risk_level:
            object_risk_level = get_risk_level(task, obj)
        # Skip the object if its risk level doesn't match the specified risk level
        if risk_level is not None and object_risk_level != risk_level:
            continue
        y_pred.append(0)
        for ix in obj['real-time eval']:
            if obj['real-time eval'][ix]["aggregated_probs"] == "N/A":
                pred_label = "N/A"
                break
            
            aggregated_probs = {opt[0]: opt[1] for opt in obj['real-time eval'][ix]["aggregated_probs"]}
            gold_option_prob = aggregated_probs.get(obj['real-time eval'][ix]["gold_option"], 0)
            if obj["env_name"] in env2prediction:
                # opts = env2prediction[obj["env_name"]]["real-time eval"][ix]["probs"]
                # probs = [opt[1] for opt in opts]
                # gold_option_prob2 = np.prod(probs)
                
                aggregated_probs2 = {opt[0]: opt[1] for opt in env2prediction[obj["env_name"]]["real-time eval"][ix]["aggregated_probs"]}
                gold_option_prob2 = aggregated_probs2.get(obj['real-time eval'][ix]["gold_option"], 0)
            else:
                print('env not found', obj["env_name"])
                gold_option_prob2 = gold_option_prob    
            ensembled_prob = (gold_option_prob + gold_option_prob2) / 2
            pos_prob = round(1.0 - ensembled_prob, 3)

            y_pred[-1] = pos_prob

            if ensembled_prob >= threshold:
                pred_label = "Correct"
            else:
                pred_label = "Incorrect"
                break

        if obj["trace_correct"]:
            y_true.append(0)
            if pred_label == "Correct":
                true_negative += 1
            else:
                # ipdb.set_trace()
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
                false_negative += 1

    return {
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "y_true": y_true,
        "y_pred": y_pred,
    }, tp_tasks, predictions
    


def evaluate_multi_step(json_objects, task, aggregated_func, threshold=0.5, risk_level=None):
    cost = 0
    true_negative, false_positive, false_negative, true_positive = 0, 0, 0, 0
    fn_envs = []
    y_true, y_pred, tp_tasks = [], [], []
    predictions = []
    for obj in json_objects:
        if risk_level:
            object_risk_level = get_risk_level(task, obj)
        # Skip the object if its risk level doesn't match the specified risk level
        if risk_level is not None and object_risk_level != risk_level:
            continue

        y_pred.append(0)
        for ix in obj['real-time eval']:
            if obj['real-time eval'][ix]["probs"]:
                probs = [opt[1] for opt in obj['real-time eval'][ix]["probs"]]
                final_prob = aggregated_func(probs)
                y_pred[-1] = 1 - final_prob
                if final_prob > threshold:
                    pred_label = "Correct"
                else:
                    pred_label = "Incorrect"
                    break
            else:
                pred_label = "N/A"
                break
        # if pred_label == 'N/A': 
        #     y_pred.pop()
        #     continue
        
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
                if task == 'WebShop':
                    try:
                        cost += float(obj["selected_product_price"][0])
                    except:
                        pass
                else:
                    cost += 1
                false_negative += 1
                fn_envs.append(obj["env_name"])
    print('cost', cost)

    return {
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "false_negative_env": fn_envs,
        "y_true": y_true,
        "y_pred": y_pred,
        "fn_envs": fn_envs
    }, tp_tasks, predictions

def evaluate_prob(json_objects):
    correct, incorrect, uncertain, total = 0, 0, 0, 0
    for obj in json_objects:
        if obj["gold_option"] in obj["aggregated_probs"][0][0]:
            if obj["trace_correct"]:
                correct += 1
            else:
                incorrect += 1
        else:
            uncertain += 1
        total += 1
    print(
        correct,
        incorrect,
        uncertain,
        correct / total,
        incorrect / total,
        uncertain / total,
        total,
    )

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

def get_eval_results(data_dir, files, kwargs):
    true_positive, true_negative, false_positive, false_negative = 0, 0, 0, 0
    y_true, y_pred, all_tp_tasks, all_predicted_pos = [], [], [], []
    false_negative_env = []
    # if kwargs['task'] == 'WebShop':
    #     with open("/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/actor-traj/WebShop/halted_files.json", 'r') as f:
    #         halted_files = json.load(f)
    # elif kwargs['task'] == 'hotpotqa':
    #     with open("/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/actor-traj/hotpotqa/halted_files.json", 'r') as f:
    #         halted_files = json.load(f)
    # else:
    halted_files = []

    for file in files:
        if "backup" in file: continue
        json_objects = convert_json_objs(os.path.join(data_dir, file))
        json_objects = [obj for obj in json_objects if obj["env_name"] + '.json' not in halted_files]
        # ipdb.set_trace()

        output, tp_tasks, predicted_pos = eval_func[args.method](json_objects, **kwargs)
        for pred in predicted_pos:
            pred.update({'folder_name': file})
        true_positive += output["true_positive"]
        true_negative += output["true_negative"]
        false_positive += output["false_positive"]
        false_negative += output["false_negative"]
        false_negative_env += output.get('false_negative_env', [])
        y_true += output["y_true"]
        y_pred += output["y_pred"]
        all_tp_tasks += tp_tasks
        all_predicted_pos += predicted_pos
    print('y true', len(y_true))

    epsilon = 1e-17
    recall = true_positive / (true_positive + false_negative + epsilon)
    precision = true_positive / (true_positive + false_positive + epsilon)
    f1 = 2 * recall * precision / (recall + precision + 1e-7)
    # auc-pr/average precision
    # neg_ix, pos_ix = [], []
    # for i, label in enumerate(y_true):
    #     if label == 0:
    #         neg_ix.append(i)
    #     else:
    #         pos_ix.append(i)

    # y_true = np.array(y_true)[neg_ix].tolist() + np.array(y_true)[pos_ix[:len(neg_ix)]].tolist()
    # y_pred = np.array(y_pred)[neg_ix].tolist() + np.array(y_pred)[pos_ix[:len(neg_ix)]].tolist()
        
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_pred)

    # recall_bins = []
    # # # bin recalls based on pr-thresholds
    # pr_thresholds = [0.5,0.6,0.7,0.8,0.9,1]
    # for i in range(1,len(pr_thresholds)):
    #     indices = np.where((precisions>=pr_thresholds[i-1]) & (precisions<pr_thresholds[i]))

    #     if indices[0].size == 0:
    #         recall_bins.append('nan')
    #     else:
    #         recall_bins.append(np.mean(recalls[indices]))
    # print('recall_bins', recall_bins)

    auc_pr = auc(recalls, precisions)
    average_precision = average_precision_score(y_true, y_pred)
    accuracy = (true_positive + true_negative) / (true_positive + true_negative + false_positive + false_negative)
    
    # auc-roc
    try:
        ece = ECE(10)
        ece_score = ece.measure(np.array(y_pred), np.array(y_true))
        auc_roc = roc_auc_score(y_true, y_pred)
    except Exception as e:
        print(e)
        auc_roc = -1
        ece_score = -1
    ipdb.set_trace()
    return { "recall": recall,
            "precision": precision,
            "f1": f1,
            "auc_pr": auc_pr,
            'precision_list': precisions.tolist(),
            'recall_list': recalls.tolist(),
            "thresholds_list": thresholds.tolist(),
            'false_neg_envs': false_negative_env,
            "accuracy": accuracy,
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "threshold": kwargs.get("threshold", ""),
            "average_precision": average_precision,
            "ece": ece_score,
            "auc_roc": auc_roc,
            "positive_count": sum(y_true),
            "negative_count": len(y_true) - sum(y_true),
            "total_count": len(y_true)}, all_tp_tasks, all_predicted_pos



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--model_type", type=str, default="gpt35-turbo", help="gpt35-turbo, gpt4-turbo")
    parser.add_argument("--method", type=str, default="self_eval", help="non-prob, self-eval, prob-multiclass, prob")
    parser.add_argument('--task', type=str, required=True)
    parser.add_argument('--threshold', type=float, default=0.0)
    parser.add_argument('--subfolder', type=str,required=True, default="")
    parser.add_argument('--risk_level', type=str, default=None)
    parser.add_argument('--ensemble_dir', type=str, default=None)
    parser.add_argument('--signature', type=str, default="")

    args = parser.parse_args()

    mapping = {"A": "D", "B": "C", "C": "B", "D": "A"}
    eval_func = {
        "non-prob": evaluate_non_prob,
        "self_eval": self_evaluation,
        "wiseacquire": evaluate_prob_multiclass,
        "self_eval_soft": self_evaluation_soft,
        "self_consistency": self_evaluation,
        "multi_step": evaluate_multi_step,
        "ensemble": evaluate_prob_multiclass_ensemble,
    }
    if args.method == "ensemble":
        data_dir = f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/{args.model_type}/{args.task}/wiseacquire/{args.subfolder}"
    else:
        data_dir = os.path.join(f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/{args.model_type}/{args.task}/{args.method}", f"{args.signature}", f"{args.subfolder}")
    files = os.listdir(data_dir)
    files = sorted(files)
    kwargs = {"risk_level": args.risk_level, 'task': args.task, "threshold": args.threshold}

    if args.method == "ensemble":
        files2 = os.listdir(args.ensemble_dir)
        files2 = sorted(files2)
        json_objects2 = []
        for file in files2:
            if "backup" in file: continue
            json_objects2.extend(convert_json_objs(os.path.join(args.ensemble_dir, file)))

        kwargs.update({"threshold": args.threshold, "json_objects2": json_objects2})

    elif args.method == "self_consistency":
        kwargs.update({"self_consistency": True})

    if args.method == "multi_step":
        result = {}
        tp_tasks = {}
        pred_pos = {}

        for func in [np.prod, np.max, np.mean, np.min]:
            kwargs["aggregated_func"] = func
            result[func.__name__], tp_tasks[func.__name__], pred_pos[func.__name__] = get_eval_results(data_dir, files, kwargs)
            
    else:
        result, tp_tasks, pred_pos = get_eval_results(data_dir, files, kwargs)

    if args.risk_level is not None:
        if args.method == "ensemble":
            save_dir = f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/{args.model_type}/{args.task}_eval_metrics/{args.method}/{args.subfolder}/{args.risk_level}_ensemble/"
        else:
            save_dir = os.path.join(f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/{args.model_type}/{args.task}_eval_metrics/{args.method}/{args.subfolder}", args.signature, f"{args.risk_level}")
    else:
        save_dir = f"/storage/ukp/work/fang/AgentTuning/AgentBench.old/outputs/evaluation_results/{args.model_type}/{args.task}_eval_metrics/{args.method}/{args.subfolder}/"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    threshold = kwargs.get("threshold", "")
    with open(os.path.join(save_dir, f"metrics{threshold}.json"), "w") as f:
        json.dump(result, f, indent=4)
    with open(os.path.join(save_dir, f"tp_tasks{threshold}.json"), "w") as f:
        json.dump(tp_tasks, f, indent=4)

    with open(os.path.join(save_dir, f"predicted_pos{threshold}.json"), "w") as f:
        json.dump(pred_pos, f, indent=4)