import json
import openai
import colors_worker


def setup_oai_worker():
    """
    Set up the OpenAI GPT-3 worker using configuration details from 'config.json'.

    This function reads configuration details from a 'config.json' file, which should include information about the
    OpenAI GPT-3 worker, such as the API key, base URL, and API version. It then configures the OpenAI Python library
    to use these details for interactions with the GPT-3 worker.

    It sets up the deployment name and other parameters required to use the OpenAI API with Azure.

    Returns:
        deployment_name (str): The name of the deployment to be used for prompt creation.
    """
    with open(r'config.json') as config_file:
        config_details = json.load(config_file)
    global deployment_name
    # Setting up the deployment name
    deployment_name = config_details['COMPLETIONS_MODEL']
    # This is set to `azure`
    openai.api_type = "azure"
    # The API key for your Azure OpenAI resource.
    openai.api_key = config_details["OPENAI_API_KEY"]
    # The base URL for your Azure OpenAI resource. e.g. "https://<your resource name>.openai.azure.com"
    openai.api_base = config_details['OPENAI_API_BASE']
    # Currently OPENAI API have the following versions available: 2022-12-01
    openai.api_version = config_details['OPENAI_API_VERSION']
    return deployment_name


deployment_name = setup_oai_worker()


def create_prompt(system_message_oai, messages_oai):
    """
    Create a conversation prompt for OpenAI's GPT-3 model.

    This function takes a system message and a list of user and assistant messages and formats them into a conversation
    prompt. The conversation prompt is used as input for the OpenAI GPT-3 model.

    Args:
        system_message_oai (str): A system message or instruction to provide context to the model.
        messages_oai (list): A list of messages with 'sender' and 'text' keys, where 'sender' can be 'user' or 'assistant'
                            and 'text' contains the message content.

    Returns:
        str: The formatted conversation prompt to be used as input for the GPT-3 model.
    """
    prompt = system_message_oai
    message_template = "\n<|im_start|>{}\n{}\n<|im_end|>"
    for message in messages_oai:
        prompt += message_template.format(message['sender'], message['text'])
    prompt += "\n<|im_start|>assistant\n"
    return prompt


def return_summary(md_file):
    """
    Summarize a markdown file using OpenAI's GPT-3 model.

    This function reads the content of a markdown file and generates a summary using the OpenAI GPT-3 model. It constructs
    a conversation prompt for the model and sends the request for summarization. The generated summary is returned.

    Args:
        md_file (str): The path to the markdown file to be summarized.

    Returns:
        str: The summarized text generated by the GPT-3 model.

    Note:
        The function constructs a conversation prompt with a system message and user message, sending the content of
        the markdown file to the GPT-3 model for summarization.

        The maximum context length of the model is 8193 characters. If the input markdown file exceeds this length, it
        will be truncated.

        The function uses specific GPT-3 parameters, including engine, temperature, max_tokens, top_p, frequency_penalty,
        presence_penalty, and stop tokens for summarization.

    """
    with open(md_file, "r") as f:
        data = f.read()
    system_message_template = "<|im_start|>system\n{}\n<|im_end|>"
    system_message = system_message_template\
        .format("You are an AI assistant that helps summarize customer support articles. "
                "Do not use line breaks and new lines. "
                "Article summary must be a single line text.")

    max_length = 8193  # Maximum context length of the model
    if len(data) > max_length:
        data = data[:max_length]
    colors_worker.prCyan(f"Summarizing: {md_file} {len(data)}")

    messages = [{"sender": "user", "text": "Summarize this article: \n" + data}]
    response = openai.Completion.create(
        engine=deployment_name,
        prompt=create_prompt(system_message, messages),
        temperature=0.7,
        max_tokens=800,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=["<|im_end|>"])
    return response.choices[0].text
