from evaluator import StandardEvaluator, MultistepEvaluator, StandardEvaluatorSC, InferAct
import argparse
import os
import json
from evaluator.utils_eval import convert_json_objs
from tqdm import tqdm
from sklearn.metrics import precision_recall_curve, auc
import numpy as np
from feedback_generator import FeedbackGenerator
from actor.alfworld.alfworld_trial import run_trial
from actor.hotpotqa.agents import ReactAgent

def run_alfworld(args, feedback_dir):

    # initialize environment configs
    env_configs = []
    for i in range(args.num_envs):
        if args.trial_num == 0:
            env_configs += [{
            'name': f'env_{i}',
            'memory': [],
            'is_success': False,
            'skip': False
            }]
        else:
            with open(os.path.join(feedback_dir, f"{i}.txt"), 'r') as f:
                feedback = f.readlines()
            if str(len(feedback)) != args.trial_num:
                env_configs += [{
                    'name': f'env_{i}',
                    'memory': [],
                    'is_success': True,
                    'skip': False
                }]
            else:
                env_configs += [{
                    'name': f'env_{i}',
                    'memory': [fed.strip() for fed in feedback],
                    'is_success': False,
                    'skip': False
                }]
            
    print(f"""
    -----
    Starting run with the following parameters:

    Number of environments: {args.num_envs}
    Use memory: {args.use_memory}

    Sending trajectories to `{args.traj_dir}`
    -----
    """)

    # run trials
    trial_log_dir: str = os.path.join(args.traj_dir, f"retrial_{args.trial_num}", args.feedback_type if int(args.trial_num) > 0 else '')

    if not os.path.exists(trial_log_dir):
        os.makedirs(trial_log_dir)

    # run trial
    run_trial(trial_log_dir, env_configs, args.use_memory, args.model_name)

def run_hotpotqa(args, feedback_dir, actor_flies_dir):
    with open("./outputs/actor-traj/hotpotqa/data.json", "r") as f:
        data = json.load(f)[:2]
    env2data = {row['env_name']: row for row in data}

    if not os.path.exists(actor_flies_dir):
        os.makedirs(actor_flies_dir)

    if args.trial_num == 0:
        # generate feedback for the first trial
        agents = [ReactAgent(row['question'], row['answer'], []) for row in data]
    else:
        agents = []
        # load feedback
        feedback_files = os.listdir(feedback_dir)
        # actor files
        actor_files = os.listdir(actor_flies_dir)

        for file in feedback_files:
            with open(os.path.join(feedback_dir, file), "r") as f:
                feedback = f.readlines()

            if len(feedback) == args.trial_num and not file.replace('.txt', '.json') in actor_files:
                question = env2data[file.replace('.txt', '')]['question']
                answer = env2data[file.replace('.txt', '')]['answer']
                agents.append(ReactAgent(question, answer, feedback))

    for i, agent in enumerate(tqdm([a for a in agents if not a.is_correct()])):
        agent.run()
        with open(os.path.join(actor_flies_dir, f"{i}.json"), "w") as f:
            json.dump(agent.output_traj(), f, ensure_ascii=False, indent=4)


# load existing evaluated data, load data from actor trajectories to evaluate
def run_evaluator(args, evaluator, actor_traj_dir, last_rejected_files, eval_dir, kwargs):

    # path to save eval results
    eval_result_dir = os.path.join(eval_dir, "eval_results")
    if not os.path.exists(eval_result_dir):
        os.makedirs(eval_result_dir)
    
    # load evaluated data
    existing_envs = []
    evaluated_file = os.path.join(eval_result_dir, f"{args.feedback_type}.txt" if args.trial_num > 0 else "init.txt")
    if os.path.exists(evaluated_file):
        entries = convert_json_objs(evaluated_file)
        existing_envs = [entry["env_name"] + '.json' for entry in entries]

    f_file = open(evaluated_file, "a")

    for file in tqdm(last_rejected_files):
        if not file.endswith(".json"):
            file = file + ".json"
        if file in existing_envs:
            print(f"{file} is already evaluated")
            continue
        kwargs["env_name"] = file.split(".")[0]

        if "config" in file:
            continue
        if not os.path.exists(os.path.join(actor_traj_dir, file)):
            print(f"there is no {os.path.join(actor_traj_dir, file)}")
            continue
        with open(os.path.join(actor_flies_dir, file), "r") as f:
            data = json.load(f)

        is_halted = data.get("is_halted", False)
        if is_halted:
            print(f"{file} is halted")
            continue
        message = data["path"]

        output = evaluator.evaluate(message, **kwargs)
        if not output:
            continue
        # add into a json object
        output["trace_correct"] = data["trace_correct"]
        if args.task == "webshop":
            output["true_item"] = data["true_item"]

        f_file.write(json.dumps(output, indent=4) + "\n")
        f_file.flush()
    f_file.close()

def cal_metrics(data_dir, files, kwargs, evaluator):
    true_positive, true_negative, false_positive, false_negative, fn_cost = 0, 0, 0, 0, 0
    y_true, y_pred, all_tp_tasks, all_predicted_pos = [], [], [], []
    false_negative_env = []

    for file in files:
        if "backup" in file: continue
        json_objects = convert_json_objs(os.path.join(data_dir, file))

        output, tp_tasks, predicted_pos = evaluator.metric(json_objects, **kwargs)
        for pred in predicted_pos:
            pred.update({'folder_name': file})
        true_positive += output["true_positive"]
        true_negative += output["true_negative"]
        false_positive += output["false_positive"]
        false_negative += output["false_negative"]
        false_negative_env += output.get('false_negative_env', [])
        y_true += output["y_true"]
        y_pred += output["y_pred"]
        fn_cost += output["fn_cost"]
        all_tp_tasks += tp_tasks
        all_predicted_pos += predicted_pos

    print('y true', len(y_true))
    epsilon = 1e-17
    recall = true_positive / (true_positive + false_negative + epsilon)
    precision = true_positive / (true_positive + false_positive + epsilon)
    f1 = 2 * recall * precision / (recall + precision + 1e-7)
    if y_pred:
        precisions, recalls, thresholds = precision_recall_curve(y_true, y_pred)
        auc_pr = auc(recalls, precisions)
        precisions = precisions.tolist()
        recalls = recalls.tolist()
        thresholds = thresholds.tolist()
    else:
        precisions, recalls, thresholds = [], [], []
        auc_pr = 0
        
    accuracy = (true_positive + true_negative) / (true_positive + true_negative + false_positive + false_negative)

    return { "recall": recall,
            "precision": precision,
            "f1": f1,
            "auc_pr": auc_pr,
            'precision_list': precisions,
            'recall_list': recalls,
            "thresholds_list": thresholds,
            'false_neg_envs': false_negative_env,
            "false_neg_cost": fn_cost,
            "accuracy": accuracy,
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "threshold": kwargs.get("threshold", ""),
            "positive_count": sum(y_true),
            "negative_count": len(y_true) - sum(y_true),
            "total_count": len(y_true)}, all_tp_tasks, all_predicted_pos


def run_metrics(args, evaluator, eval_dir):
    eval_metric_dir = os.path.join(eval_dir, "eval_metrics", args.feedback_type if args.trial_num > 0 else "init")
    if not os.path.exists(eval_metric_dir):
        os.makedirs(eval_metric_dir)
    eval_result_dir = os.path.join(eval_dir, "eval_results")
    files = os.listdir(eval_result_dir)
    files = sorted(files)

    kwargs = {'threshold': args.threshold, 'task': args.task}
    if args.eval_method == "multi_step":
        result = {}
        tp_tasks = {}
        pred_pos = {}
        for func in [np.prod, np.max, np.mean, np.min]:
            kwargs["aggregated_func"] = func
            result[func.__name__], tp_tasks[func.__name__], pred_pos[func.__name__] = cal_metrics(eval_result_dir, files, kwargs)
    else:
        result, tp_tasks, pred_pos = cal_metrics(eval_result_dir, files, kwargs, evaluator)
    threshold = kwargs.get("threshold", "")
    with open(os.path.join(eval_metric_dir, f"predicted_pos{threshold}.json"), "w") as f:
        json.dump(pred_pos, f, indent=4)
    
    with open(os.path.join(eval_metric_dir, f"metrics{threshold}.json"), "w") as f:
        json.dump(result, f, indent=4)

    with open(os.path.join(eval_metric_dir, f"tp_tasks{threshold}.json"), "w") as f:
        json.dump(tp_tasks, f, indent=4)

    with open(os.path.join(eval_metric_dir, f"predicted_pos{threshold}.json"), "w") as f:
        json.dump(pred_pos, f, indent=4)

if __name__ == "__main__":
    # add argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="gpt4-turbo", help="model name, gpt4-turbo, gpt35-turbo")
    parser.add_argument("--model_path", type=str, default="", help="path to the local model")
    parser.add_argument("--eval_method", type=str, default="standard", help="standard, multistep, standard_sc, inferact")
    parser.add_argument(
        "--save_dir",
        type=str,
        default="./outputs/evaluation_results",
    )
    parser.add_argument("--feedback_type", type=str, default="none", help="results with different feedback types, nl, binary")
    parser.add_argument("--task", type=str, default="", required=True)
    parser.add_argument("--trial_num", type=int, default=0)
    parser.add_argument("--risk_mode", action="store_true", help="sensitive mode")
    parser.add_argument("--signature", type=str, default="")
    parser.add_argument("--threshold", type=str, default="")
    parser.add_argument("--traj_dir", type=str, default="./outputs/actor-traj")
    ## args for Alfworld
    parser.add_argument("--num_envs", type=int, help="The number of environments per trial")
    parser.add_argument("--use_memory", action='store_true', help="Allow the Agent to use memory")
    ## actions
    parser.add_argument("--run_agents", action="store_true", help="run agents")
    parser.add_argument("--do_feedback_gen", action="store_true", help="generate nl feedback for rejected envs")
    parser.add_argument("--do_eval", action="store_true", help="run evaluation")

    args = parser.parse_args()

    assert args.eval_method in ["standard", "multistep", "standard_sc", "inferact"], "eval_method should be one of standard, multistep, standard_sc, inferact"

    kwargs = {"model_path": args.model_path, "model_name": args.model_name, "risk_mode": args.risk_mode}

    if args.eval_method == "self_consistency":
        kwargs["temperature"] = 0.7

    evaluators = {"standard": StandardEvaluator, "multistep": MultistepEvaluator, "standard_sc": StandardEvaluatorSC, "inferact": InferAct}
    evaluator = evaluators[args.eval_method](args.task, **kwargs)

    if args.model_name == "gpt4-turbo":
        save_dir = args.save_dir + "/gpt4-turbo"

    elif args.model_name == "gpt35-turbo":
        save_dir = args.save_dir + "/gpt35-turbo"

    elif args.model_name == 'llama-3-70B':
        save_dir = args.save_dir + "/llama-3-70B"


    ## All paths
    eval_dir = os.path.join(save_dir, args.task, args.eval_method, args.signature, f"retrial_{args.trial_num}" if not args.risk_mode else f"retrial_{args.trial_num}_sensitive")
    actor_flies_dir = (
        f"{args.traj_dir}/{args.task}/retrial_{args.trial_num}/{args.feedback_type if args.trial_num > 0 else ''}"
    )
    feedback_dir = os.path.join("./outputs/feedbacks", args.task,  args.feedback_type)

    if args.run_agents:
        if args.task == "alfworld":
            run_alfworld(args, feedback_dir)
        elif args.task == "hotpotqa":
            run_hotpotqa(args, feedback_dir, actor_flies_dir)


    last_rejected_files = []
    # associated with different evaluators
    last_rejected_path = os.path.join(
            eval_dir.replace(f"retrial_{args.trial_num}", f"retrial_{max(args.trial_num - 1, 0)}"),
            "eval_metrics",
            args.feedback_type if args.trial_num > 1 else "init",
            f"predicted_pos{args.threshold}.json"
        )
    if args.trial_num > 0:    
        with open(last_rejected_path, "r") as f:
            last_rejected = json.load(f)

        if args.eval_method == "multi_step":
            last_rejected = last_rejected['prod']

        for f in last_rejected:
            if f['true_label'] == 'Incorrect':
                last_rejected_files.append((f['env_name']))
    else:
        last_rejected_files = os.listdir(actor_flies_dir)
        last_rejected_files = sorted(last_rejected_files)




    if args.do_eval:
        run_evaluator(args, evaluator, actor_flies_dir, last_rejected_files, eval_dir, kwargs)
        # calculate F1 score, auc-pr
        run_metrics(args, evaluators[args.eval_method], eval_dir)

    if args.do_feedback_gen:
        # generate nl feedback for rejected envs
        kwargs = {"feedback_dir": feedback_dir, "last_rejected_path": last_rejected_path, "actor_traj_dir": actor_flies_dir, "trial_num": args.trial_num}
        
        if args.task == "alfworld":
            kwargs["expert_traj_dir"] = "./actor/alfworld/expert_traj"

        feedback_generator = FeedbackGenerator(task=args.task, feedback_type=args.feedback_type, eval_method=args.eval_method, threshold=args.threshold, **kwargs)
        feedback_generator.generate_feedback()