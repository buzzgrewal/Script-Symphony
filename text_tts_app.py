import re
import torch
import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer
import torchaudio
from zonos.model import Zonos
from zonos.conditioning import make_cond_dict
import os

text_model_name = "mistralai/Mistral-7B-Instruct-v0.2" 
tokenizer = AutoTokenizer.from_pretrained(text_model_name)
text_model = AutoModelForCausalLM.from_pretrained(
    text_model_name, torch_dtype=torch.float16, device_map="auto"
)

device = "cuda" if torch.cuda.is_available() else "cpu"
tts_model = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device=device)
reference_audio_path = "reference_audio.mp3"

def segment_script(script_text: str):
    pattern = r"(?i)(?=\b(INT\.|EXT\.)\b)"
    scenes = re.split(pattern, script_text)

    scene_list = []
    current_scene = ""
    for token in scenes:
        if re.match(r"(?i)^(INT\.|EXT\.)", token.strip()):
            if current_scene:
                scene_list.append(current_scene.strip())
            current_scene = token.strip()
        else:
            current_scene += " " + token.strip()
    if current_scene:
        scene_list.append(current_scene.strip())
    return scene_list



def generate_scene_story(scene: str, style: str = "default") -> str:
    prompt = (
        f"Transform the following screenplay scene into a detailed, immersive narrative with a {style} tone. "
        "Focus on character emotions, setting details, and internal monologues to bring the scene to life:\n\n"
        f"{scene}\n\n"
        "Narrative:"
    )
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    output = text_model.generate(**inputs, max_length=1024, do_sample=True, temperature=0.8)
    story_segment = tokenizer.decode(output[0], skip_special_tokens=True)
    return story_segment.strip()


def generate_full_story(script: str, style: str = "default") -> str:
    scenes = segment_script(script)
    if not scenes:
        return "No scenes detected. Please check the script format."

    narrative_segments = []
    for idx, scene in enumerate(scenes):
        print(f"Processing Scene {idx+1}/{len(scenes)}...")
        segment_story = generate_scene_story(scene, style=style)
        narrative_segments.append(f"Scene {idx+1}:\n{segment_story}\n")
    full_story = "\n".join(narrative_segments)
    return full_story


def text_to_speech_zonos(text: str, output_filename: str = "output.wav", language: str = "en-us", emotion: str = "neutral") -> str:
    wav, sampling_rate = torchaudio.load(reference_audio_path)
    speaker = tts_model.make_speaker_embedding(wav, sampling_rate)

    torch.manual_seed(421)

    cond_dict = make_cond_dict(
        text=text,
        speaker=speaker,
        language=language,
        emotion=emotion 
    )
    conditioning = tts_model.prepare_conditioning(cond_dict)

    codes = tts_model.generate(conditioning)
    wavs = tts_model.autoencoder.decode(codes).cpu()

    torchaudio.save(output_filename, wavs[0], tts_model.autoencoder.sampling_rate)
    return output_filename


def process_script(script_text: str, style: str, emotion: str) -> (str, str):
    story = generate_full_story(script_text, style=style)
    audio_file = text_to_speech_zonos(story, emotion=emotion)
    return story, audio_file


def split_after_narrative(text: str) -> str:
    split_token = "Narrative:"
    idx = text.find(split_token)
    if idx != -1:
        return text[idx + len(split_token):].strip()
    else:
        return text



script_input = gr.Textbox(lines=10, label="Paste your Screenplay")
style_input = gr.Dropdown(choices=["default", "dramatic", "poetic"], label="Narrative Style")
emotion_input = gr.Dropdown(choices=["neutral", "happy", "sad", "excited", "angry"], label="Emotion for TTS")

story_output = gr.Textbox(label="Generated Story")
audio_output = gr.Audio(label="Listen to the Story", type="filepath")

iface = gr.Interface(
    fn=process_script,
    inputs=[script_input, style_input, emotion_input],
    outputs=[story_output, audio_output],
    title="Script Symphony",
    description="From Screen to Sound—Unfold Your Story into an Epic Narrative!"
)

iface.launch()