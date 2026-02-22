import google.generativeai as genai

genai.configure(api_key="AIzaSyBqpzahCaSPI4P7QZyVWxTluAsmnpJOfCg")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)