from llm import AnyOpenAILLM, LocalLLM

class BaseEvaluator:
    def __init__(self, task, **kwargs) -> None:
        self.task = task
        assert task in ['webshop', 'hotpotqa', 'alfworld'], f"your task should be one of ['webshop', 'hotpotqa', 'alfworld']"
        if "gpt" in kwargs["model_name"]:
            
            self.base_model = AnyOpenAILLM(
                model_name=kwargs.get("model_name", "gpt4-turbo"),
                model_kwargs={"temperature": kwargs.get("temperature", 0.0), "max_tokens": kwargs.get("max_tokens", 500)})
        
        elif "llama" in kwargs["model_name"]:
            self.base_model = LocalLLM(
                model_pth=kwargs["model_path"],
                temperature=kwargs.get("temperature", 0.0),
                tokenizer_pth=kwargs["model_path"],
                max_new_tokens=kwargs.get("max_tokens", 500),
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

    def generate_mapping(self, num_choices):
        # Generate a list of options
        options = list('ABCDE'[:num_choices])
        
        # Generate the mapping
        mapping = {options[i]: options[-(i+1)] for i in range(num_choices)}
        
        return mapping

    def evaluate(self, message, **kwargs):
        return NotImplementedError
    
    @classmethod
    def metric(self, **kwargs):
        return NotImplementedError
    