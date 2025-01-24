import openai

openai.api_key = "your_actual_openai_api_key"

try:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ],
        max_tokens=150,
        temperature=0.7,
    )
    print(response['choices'][0]['message']['content'])
except Exception as e:
    print(f"Error: {str(e)}")
