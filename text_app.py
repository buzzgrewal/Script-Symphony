import re
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


model_name = "mistralai/Mistral-7B-Instruct-v0.2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, device_map="auto")


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
    output = model.generate(**inputs, max_length=1024, do_sample=True, temperature=0.8)
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



def split_after_narrative(text: str) -> str:
    split_token = "Narrative:"
    idx = text.find(split_token)
    if idx != -1:
        return text[idx + len(split_token):].strip()
    else:
        return text


import gradio as gr

def create_interface():
    def process_script(script, style, progress=gr.Progress()):
        progress(0, desc="Initializing...")

        progress(0.2, desc="Segmenting scenes...")
        scenes = segment_script(script)

        full_story = []
        for idx, scene in enumerate(scenes):
            progress((idx+1)/len(scenes), desc=f"Processing Scene {idx+1}/{len(scenes)}")
            segment = generate_scene_story(scene, style)
            clean_segment = split_after_narrative(segment)
            full_story.append(f"SCENE {idx+1}:\n{clean_segment}")

        progress(1.0, desc="Finalizing...")
        return "\n\n".join(full_story)

    with gr.Blocks(theme=gr.themes.Soft(), title="Script-Symphony") as interface:
        gr.Markdown("# 🎬 Script-Symphony")
        gr.Markdown("From Screen to Sound—Unfold Your Story into an Epic Narrative!")

        with gr.Row():
            with gr.Column(scale=2):
                input_script = gr.Textbox(
                    label="Screenplay Input",
                    placeholder="Paste your screenplay here...",
                    lines=15,
                    elem_id="input-box"
                )
                style_select = gr.Dropdown(
                    choices=["Dramatic", "Suspenseful", "Romantic", "Neutral"],
                    value="Dramatic",
                    label="Narrative Style"
                )
                submit_btn = gr.Button("Convert to Novel", variant="primary")

            with gr.Column(scale=3):
                output_story = gr.Textbox(
                    label="Generated Narrative",
                    lines=20,
                    interactive=False,
                    elem_id="output-box"
                )

        examples = gr.Examples(
            examples=[[
                """INT. COFFEE SHOP - DAY
Alice fidgets with her cup. Bob enters, looking anxious.""",
                "Dramatic"
            ]],
            inputs=[input_script, style_select]
        )

        submit_btn.click(
            fn=process_script,
            inputs=[input_script, style_select],
            outputs=output_story
        )

        clear_btn = gr.ClearButton([input_script, output_story])
        gr.Markdown("### Tips:\n- Use proper screenplay formatting with INT/EXT headings\n- Keep scenes under 500 words for best results\n- Adjust style for different emotional tones")

    return interface

if __name__ == "__main__":
    interface = create_interface()
    interface.launch(share=True)