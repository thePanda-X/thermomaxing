from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import dotenv
import os
import requests
import html2text
import json
import re
from typing import Callable, Optional, Dict, Any

dotenv.load_dotenv()

class RecipeImporter:
    def __init__(self, status_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        # status_callback receives structured step events
        self.status_callback = status_callback or (lambda x: print(x))
        self.ollama_url = "http://localhost:11434/api/generate"
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")

    def emit_step(self, step: str, status: str, detail: Optional[str] = None):
        payload = {"step": step, "status": status}
        if detail:
            payload["detail"] = detail
        self.status_callback(payload)

    def query_ollama_stream(self, prompt: str, schema: str, description: str, step_name: str) -> dict:
        full_prompt = f"""
        You are an expert data extraction assistant for Thermomix recipes.
        Extract data from the text below and return it as strictly valid JSON.
        
        Follow this Schema strictly:
        {schema}

        Return ONLY the JSON object. Do not use markdown blocks.

        CONTENT:
        {prompt}
        """

        response = requests.post(
            self.ollama_url, 
            json={"model": self.ollama_model, "prompt": full_prompt, "stream": True, "format": "json"},
            stream=True
        )
        
        response.raise_for_status()
        full_response_text = ""
        
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                try:
                    json_chunk = json.loads(decoded_line)
                    token = json_chunk.get("response", "")
                    print(token, end='', flush=True)
                    full_response_text += token
                    if json_chunk.get("done", False): break
                except ValueError: continue

        print("\n")
        clean_json_str = re.sub(r"```json\s*|\s*```", "", full_response_text).strip()
        try:
            return json.loads(clean_json_str)
        except json.JSONDecodeError as e:
            self.emit_step(step_name, "failed", f"Failed to parse JSON for {description}.")
            raise e

    def extract_metadata_and_ingredients(self, markdown_content: str) -> dict:
        schema = """
        {
            "title": "Recipe Title",
            "prep_time_hours": "0",
            "prep_time_minutes": "10",
            "total_time_hours": "0",
            "total_time_minutes": "45",
            "ingredients": [
                {"name": "ingredient name", "quantity": "amount (number)", "unit": "g/ml/tsp/etc (string)"}
            ]
        }
        """
        return self.query_ollama_stream(markdown_content, schema, "Extracting Ingredients & Metadata", "extract_ingredients")

    def extract_steps(self, markdown_content: str) -> dict:
        schema = """
        {
            "steps": [
                {
                    "description": "Full text of the step instruction",
                    "minutes": "0 (string)",
                    "seconds": "0 (string)",
                    "temperature": "Temp in Celsius (e.g. '100', '120', 'Varoma') or empty string",
                    "speed": "0-10 or 'spoon' (string)",
                    "direction": "'forward' or 'reverse'"
                }
            ]
        }
        """
        prompt_addition = f"""
        RULES FOR STEPS:
        1. Extract cooking settings (Time, Temp, Speed) if explicitly stated.
        2. If a step says "Cook 5 min / 100°C / Speed 1", extract: minutes="5", temperature="100", speed="1".
        3. Direction is "forward" unless "Reverse" or "Giro Inverso" is mentioned.
        
        RECIPE TEXT:
        {markdown_content}
        """
        return self.query_ollama_stream(prompt_addition, schema, "Extracting Steps", "analyze_instructions")

    def normalize_direction(self, direction: str) -> str:
        direction = str(direction).lower().strip()
        if direction in ["reverse", "ccw", "counterclockwise", "giro inverso", "inverso", "izquierda"]:
            return "CCW"
        return "CW"

    def login_cookidoo(self, username: str, password: str, page: Page) -> None:
        if page.locator("a[class*='logout']").count() > 0:
            self.emit_step("save_to_collection", "in_progress", "Already logged in.")
            return

        self.emit_step("save_to_collection", "in_progress", "Navigating to Cookidoo...")
        page.goto("https://cookidoo.es/")
        try:
            page.locator("button#onetrust-reject-all-handler").click(timeout=3000)
        except: pass 

        self.emit_step("save_to_collection", "in_progress", "Logging in...")
        page.locator("a[class*='login']").click()
        page.locator("input#username").fill(username)
        page.locator("input#password").fill(password)
        page.locator("button#login-submit-btn").click()
        self.emit_step("save_to_collection", "in_progress", "Login process completed.")

    def create_recipe(self, page: Page, data: dict) -> None:
        self.emit_step("save_to_collection", "in_progress", "Opening recipe creator...")
        page.goto("https://cookidoo.es/created-recipes")
        page.wait_for_load_state("networkidle")
        
        if page.locator("#floating-button").count() > 0:
            page.locator("#floating-button").click()
        
        page.locator("button#create-button").click()
        page.locator("input#recipe-title").fill(data.get("title", "Imported Recipe"))
        page.locator("button[class*='button--primary']").nth(1).click()

        # Times
        page.locator("div.cr-recipe-settings-tiles__item.cr-recipe-settings-tiles__item--empty").first.click()
        page.locator("input[aria-describedby='prepTime-hours-validation']").fill(str(data.get("prep_time_hours", "0")))
        page.locator("input[aria-describedby='prepTime-minutes-validation']").fill(str(data.get("prep_time_minutes", "10")))

        page.locator("button#totalTime").first.click()
        page.locator("input[aria-describedby='totalTime-hours-validation']").fill(str(data.get("total_time_hours", "1")))
        page.locator("input[aria-describedby='totalTime-minutes-validation']").fill(str(data.get("total_time_minutes", "0")))

        page.locator("button[action='confirm']").first.click()
        page.locator("a.button--secondary").first.click()
        page.wait_for_load_state("networkidle")
        page.locator("button#add-steps").click()

        self.emit_step("save_to_collection", "in_progress", "Adding steps to Cookidoo...")
        for index, step in enumerate(data.get("steps", [])):
            self.add_step(page, step, index)

        self.emit_step("save_to_collection", "in_progress", "Adding ingredients to Cookidoo...")
        for index, ingredient in enumerate(data.get("ingredients", [])):
            self.add_ingredient(page, ingredient, index)

        self.emit_step("save_to_collection", "in_progress", "Saving recipe...")
        page.wait_for_timeout(1000)
        if page.locator("a.button--primary.cr-visible-on-desktop.cr-edit-tabs__confirm-button:visible").count() > 0:
            page.locator("a.button--primary.cr-visible-on-desktop.cr-edit-tabs__confirm-button:visible").first.click()
            self.emit_step("save_to_collection", "completed", "Recipe saved successfully.")

    def add_ingredient(self, page: Page, ingredient: dict, item_index: int) -> None:
        name = ingredient.get("name", "")
        qty = str(ingredient.get("quantity", ""))
        unit = ingredient.get("unit", "")
        ingredient_str = f"{name} {qty} {unit}".strip()
        
        input_field = page.locator("div#ingredients-tab").locator(f"cr-text-field[index='{item_index}'][contenteditable='true']")
        input_field.fill(ingredient_str)
        input_field.press("Enter")
        input_field.evaluate("(el) => el.dispatchEvent(new Event('input', { bubbles: true }))", input_field)
        input_field.evaluate("el => el.blur()")

    def add_step(self, page: Page, step: dict, step_index: int) -> None:
        desc = step.get("description", "")
        minutes = str(step.get("minutes", "0"))
        seconds = str(step.get("seconds", "0"))
        
        # Normalize Temperature
        raw_temp = str(step.get("temperature", "")).strip()
        temp_setting = None
        if raw_temp:
            if re.match(r'^\d+$', raw_temp):
                temp_setting = raw_temp
            else:
                temp_setting = "Varoma"

        # Normalize Speed
        raw_speed = str(step.get("speed", "")).strip()
        if re.match(r'^\d+(\.\d+)?$', raw_speed):
            speed_setting = raw_speed
        else:
            speed_setting = "soft"

        direction = self.normalize_direction(step.get("direction", "CW"))
        
        page.locator("div#preparation-steps-tab").locator(f"cr-text-field[index='{step_index}'][contenteditable='true']").fill(desc)
        page.locator("div#preparation-steps-tab").locator("span.icon--speed:visible").first.click()

        # Time
        page.locator(f"input[aria-describedby='minutes']").fill(minutes)
        page.locator(f"input[aria-describedby='seconds']").fill(seconds)

        # Temperature (Skip if None)
        if temp_setting:
            page.locator("cr-tts-temperature").locator("button[aria-controls='setting-panel']").click()
            page.locator(f"label[for='temperature-radio-{temp_setting}']").click()

        # Speed and Direction
        page.locator("cr-tts-speed").locator("button[aria-controls='setting-panel']").click()
        page.locator(f"label[for='direction-radio-{direction}']").click()
        page.locator(f"label[for='speed-radio-{speed_setting}']").click()

        # Save
        page.locator("div#preparation-steps-tab").locator("button.cr-popover-modal__save.button--icon.button--primary").first.click()
        page.locator("div#preparation-steps-tab").locator("button[class*='cr-manage-list__add-button']").first.click()

    def fetch_recipe_from_url(self, url: str) -> str:
        self.emit_step("fetch_recipe", "in_progress", f"Fetching {url}")
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'svg', 'form']):
            element.decompose()

        selectors = ["div.wprm-recipe-container", "div.tasty-recipes", "div.mv-create-card", "div.recipe-card", "div.recipe-content", "article", "main", ".post-content"]
        target_content = None
        for selector in selectors:
            found = soup.select_one(selector)
            if found:
                self.emit_step("fetch_recipe", "in_progress", f"Recipe container found: {selector}")
                target_content = found
                break
        
        if not target_content: target_content = soup.body

        h = html2text.HTML2Text()
        h.ignore_links = True; h.ignore_images = True; h.body_width = 0
        return h.handle(str(target_content))

    def run(self, recipe_url: str):
        self.emit_step("fetch_recipe", "in_progress", "Starting import process...")

        try:
            markdown_content = self.fetch_recipe_from_url(recipe_url)
            self.emit_step("fetch_recipe", "completed")
        except Exception as e:
            self.emit_step("fetch_recipe", "failed", f"Error fetching URL: {e}")
            return

        self.emit_step("extract_ingredients", "in_progress", "Extracting ingredients and metadata...")
        try:
            ingredients_data = self.extract_metadata_and_ingredients(markdown_content)
            self.emit_step("extract_ingredients", "completed")
        except Exception as e:
            self.emit_step("extract_ingredients", "failed", f"Ingredients extraction failed: {e}")
            return

        self.emit_step("analyze_instructions", "in_progress", "Analyzing instructions...")
        try:
            steps_data = self.extract_steps(markdown_content)
            self.emit_step("analyze_instructions", "completed")
        except Exception as e:
            self.emit_step("analyze_instructions", "failed", f"Steps extraction failed: {e}")
            return

        full_recipe_data = {**ingredients_data, **steps_data}
        self.emit_step("save_to_collection", "in_progress", f"Saving '{full_recipe_data.get('title', 'recipe')}' to Cookidoo...")

        try:
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True)
                page = browser.new_page(viewport={"width": 1400, "height": 800})
                self.login_cookidoo(os.getenv("COOKIDOO_USERNAME"), os.getenv("COOKIDOO_PASSWORD"), page)
                self.create_recipe(page, full_recipe_data)
                browser.close()
        except Exception as e:
            self.emit_step("save_to_collection", "failed", f"Failed to save recipe: {e}")
            return

        self.status_callback({"event": "done"})

        self.status_callback({"event": "done"})

