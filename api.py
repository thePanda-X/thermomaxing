from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import dotenv
import os
import requests
import html2text
import json
import re
import logging
from datetime import datetime
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)

DEBUG_DIR = "debug_output"


def save_debug_file(step_name: str, data: Any, prefix: str = "response") -> None:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{DEBUG_DIR}/{prefix}_{step_name}_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.debug(f"Saved debug file: {filename}")


dotenv.load_dotenv()


class RecipeImporter:
    def __init__(
        self, status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        # status_callback receives structured step events
        self.status_callback = status_callback or (lambda x: print(x))
        self.ollama_url = "http://localhost:11434/api/generate"
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")

    def emit_step(self, step: str, status: str, detail: Optional[str] = None):
        payload = {"step": step, "status": status}
        if detail:
            payload["detail"] = detail
        self.status_callback(payload)
        logger.info(f"[{step}] {status}: {detail or ''}")

    def query_ollama_stream(
        self, prompt: str, schema: str, description: str, step_name: str
    ) -> dict:
        logger.info(f"Querying Ollama for: {description}")
        full_prompt = f"""
        You are an expert data extraction assistant for Thermomix recipes.
        Extract data from the text below and return it as strictly valid JSON.
        
        Follow this Schema strictly:
        {schema}

        Return ONLY the JSON object. Do not use markdown blocks.

        CONTENT:
        {prompt}
        """

        save_debug_file(
            step_name,
            {"prompt": full_prompt, "description": description},
            prefix="prompt",
        )

        response = requests.post(
            self.ollama_url,
            json={
                "model": self.ollama_model,
                "prompt": full_prompt,
                "stream": True,
                "format": "json",
            },
            stream=True,
        )

        response.raise_for_status()
        full_response_text = ""

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode("utf-8")
                try:
                    json_chunk = json.loads(decoded_line)
                    token = json_chunk.get("response", "")
                    full_response_text += token
                    if json_chunk.get("done", False):
                        break
                except ValueError:
                    continue

        save_debug_file(
            step_name, {"raw_response": full_response_text}, prefix="raw_response"
        )

        clean_json_str = re.sub(r"```json\s*|\s*```", "", full_response_text).strip()
        try:
            result = json.loads(clean_json_str)
            save_debug_file(step_name, result, prefix="parsed")
            return result
        except json.JSONDecodeError as e:
            self.emit_step(
                step_name, "failed", f"Failed to parse JSON for {description}."
            )
            logger.error(f"JSON parse error for {description}: {e}")
            save_debug_file(
                step_name,
                {"error": str(e), "clean_json": clean_json_str},
                prefix="error",
            )
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
        return self.query_ollama_stream(
            markdown_content,
            schema,
            "Extracting Ingredients & Metadata",
            "extract_ingredients",
        )

    def extract_steps(self, markdown_content: str) -> dict:
        schema = """
        {
            "steps": [
                {
                    "description": "Full text of the step instruction",
                    "use_thermomix": "true if this step uses the Thermomix, false if it mentions using external devices (pan, stove, oven, blender, etc.)",
                    "minutes": "0 (string) - only set if use_thermomix is true",
                    "seconds": "0 (string) - only set if use_thermomix is true",
                    "temperature": "Temp in Celsius (e.g. '100', '120', 'Varoma') or empty string - only set if use_thermomix is true",
                    "speed": "0-10 or 'spoon' (string) - only set if use_thermomix is true",
                    "direction": "'forward' or 'reverse' - only set if use_thermomix is true"
                }
            ]
        }
        """
        prompt_addition = f"""
        RULES FOR STEPS:
        1. Set use_thermomix to FALSE if the step mentions using ANY external device (pan, stove, oven, microwave, blender, food processor, separate pot, grill, etc.). Leave all other fields empty for these steps.
        2. Set use_thermomix to TRUE only if the step uses the Thermomix blade or bowl directly.
        3. For Thermomix steps, extract cooking settings (Time, Temp, Speed) if explicitly stated.
        4. If a step says "Cook 5 min / 100°C / Speed 1", extract: use_thermomix=true, minutes="5", temperature="100", speed="1".
        5. If a step says "Boil water in a separate pot" or "Bake in oven at 180°C", extract: use_thermomix=false, description="Boil water in a separate pot" (or whatever the instruction is).
        6. Direction is "forward" unless "Reverse" or "Giro Inverso" is mentioned.

        RECIPE TEXT:
        {markdown_content}
        """
        return self.query_ollama_stream(
            prompt_addition, schema, "Extracting Steps", "analyze_instructions"
        )

    def normalize_direction(self, direction: str) -> str:
        direction = str(direction).lower().strip()
        if direction in [
            "reverse",
            "ccw",
            "counterclockwise",
            "giro inverso",
            "inverso",
            "izquierda",
        ]:
            return "CCW"
        return "CW"

    def login_cookidoo(self, username: str, password: str, page: Page) -> None:
        if page.locator("a[class*='logout']").count() > 0:
            self.emit_step("save_to_collection", "in_progress", "Already logged in.")
            return

        logger.info("Logging in to Cookidoo...")
        self.emit_step("save_to_collection", "in_progress", "Navigating to Cookidoo...")
        page.goto("https://cookidoo.es/")
        try:
            page.locator("button#onetrust-reject-all-handler").click(timeout=3000)
        except:
            pass

        self.emit_step("save_to_collection", "in_progress", "Logging in...")
        page.locator("a[class*='login']").click()
        page.locator("input#username").fill(username)
        page.locator("input#password").fill(password)
        page.locator("button#login-submit-btn").click()
        self.emit_step("save_to_collection", "in_progress", "Login process completed.")
        logger.info("Login successful")

    def create_recipe(self, page: Page, data: dict) -> None:
        title = data.get("title", "Imported Recipe")
        logger.info(f"Creating recipe: {title}")
        self.emit_step("save_to_collection", "in_progress", "Opening recipe creator...")
        page.goto("https://cookidoo.es/created-recipes")
        page.wait_for_load_state("networkidle")

        if page.locator("#floating-button").count() > 0:
            page.locator("#floating-button").click()

        page.locator("button#create-button").click()
        page.locator("input#recipe-title").fill(data.get("title", "Imported Recipe"))
        page.locator("button[class*='button--primary']").nth(1).click()

        # Times
        page.locator(
            "div.cr-recipe-settings-tiles__item.cr-recipe-settings-tiles__item--empty"
        ).first.click()
        page.locator("input[aria-describedby='prepTime-hours-validation']").fill(
            str(data.get("prep_time_hours", "0"))
        )
        page.locator("input[aria-describedby='prepTime-minutes-validation']").fill(
            str(data.get("prep_time_minutes", "10"))
        )

        page.locator("button#totalTime").first.click()
        page.locator("input[aria-describedby='totalTime-hours-validation']").fill(
            str(data.get("total_time_hours", "1"))
        )
        page.locator("input[aria-describedby='totalTime-minutes-validation']").fill(
            str(data.get("total_time_minutes", "0"))
        )

        page.locator("button[action='confirm']").first.click()
        page.locator("a.button--secondary").first.click()
        page.wait_for_load_state("networkidle")
        page.locator("button#add-steps").click()

        self.emit_step(
            "save_to_collection", "in_progress", "Adding steps to Cookidoo..."
        )
        logger.info(f"Adding {len(data.get('steps', []))} steps to recipe")
        for index, step in enumerate(data.get("steps", [])):
            self.add_step(page, step, index)

        logger.info(f"Adding {len(data.get('ingredients', []))} ingredients to recipe")
        self.emit_step(
            "save_to_collection", "in_progress", "Adding ingredients to Cookidoo..."
        )
        for index, ingredient in enumerate(data.get("ingredients", [])):
            self.add_ingredient(page, ingredient, index)

        self.emit_step("save_to_collection", "in_progress", "Saving recipe...")
        page.wait_for_timeout(1000)
        if (
            page.locator(
                "a.button--primary.cr-visible-on-desktop.cr-edit-tabs__confirm-button:visible"
            ).count()
            > 0
        ):
            page.locator(
                "a.button--primary.cr-visible-on-desktop.cr-edit-tabs__confirm-button:visible"
            ).first.click()
            logger.info(f"Recipe '{title}' saved successfully")
            self.emit_step(
                "save_to_collection", "completed", "Recipe saved successfully."
            )

    def add_ingredient(self, page: Page, ingredient: dict, item_index: int) -> None:
        name = ingredient.get("name", "")
        qty = str(ingredient.get("quantity", ""))
        unit = ingredient.get("unit", "")
        ingredient_str = f"{name} {qty} {unit}".strip()

        input_field = page.locator("div#ingredients-tab").locator(
            f"cr-text-field[index='{item_index}'][contenteditable='true']"
        )
        input_field.fill(ingredient_str)
        input_field.press("Enter")
        input_field.evaluate(
            "(el) => el.dispatchEvent(new Event('input', { bubbles: true }))",
            input_field,
        )
        input_field.evaluate("el => el.blur()")

    def add_step(self, page: Page, step: dict, step_index: int) -> None:
        desc = step.get("description", "")
        use_thermomix = step.get("use_thermomix", True)

        if not use_thermomix:
            logger.info(
                f"Step {step_index + 1}: External device step - adding as plain text"
            )
            input_field = page.locator("div#preparation-steps-tab").locator(
                f"cr-text-field[index='{step_index}'][contenteditable='true']"
            )
            input_field.fill(desc)
            input_field.press("Enter")
            return

        minutes = str(step.get("minutes", "0"))
        seconds = str(step.get("seconds", "0"))

        # Normalize Temperature
        raw_temp = str(step.get("temperature", "")).strip()
        temp_setting = None
        if raw_temp:
            if re.match(r"^\d+$", raw_temp):
                temp_setting = raw_temp
            else:
                temp_setting = "Varoma"

        # Normalize Speed
        raw_speed = str(step.get("speed", "")).strip()
        if re.match(r"^\d+(\.\d+)?$", raw_speed):
            speed_setting = raw_speed
        else:
            speed_setting = "soft"

        direction = self.normalize_direction(step.get("direction", "CW"))

        input_field = page.locator("div#preparation-steps-tab").locator(
            f"cr-text-field[index='{step_index}'][contenteditable='true']"
        )
        input_field.fill(desc)
        page.locator("div#preparation-steps-tab").locator(
            "span.icon--speed:visible"
        ).first.click()

        # Time
        if minutes == "0" and seconds == "0":
            seconds = "1"
        page.locator("input[aria-describedby='minutes']").fill(minutes)
        page.locator("input[aria-describedby='seconds']").fill(seconds)

        # Temperature (Skip if None)
        if temp_setting:
            page.locator("cr-tts-temperature").locator(
                "button[aria-controls='setting-panel']"
            ).click()
            page.locator(f"label[for='temperature-radio-{temp_setting}']").click()

        # Speed and Direction
        if speed_setting:
            page.locator("cr-tts-speed").locator(
                "button[aria-controls='setting-panel']"
            ).click()
            page.locator(f"label[for='direction-radio-{direction}']").click()
            page.locator(f"label[for='speed-radio-{speed_setting}']").click()

        # Save and move to next
        page.locator("div#preparation-steps-tab").locator(
            "button.cr-popover-modal__save.button--icon.button--primary"
        ).first.click()
        input_field.press("Enter")

    def fetch_recipe_from_url(self, url: str) -> str:
        logger.info(f"Fetching recipe from: {url}")
        self.emit_step("fetch_recipe", "in_progress", f"Fetching {url}")
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside",
                "iframe",
                "svg",
                "form",
            ]
        ):
            element.decompose()

        selectors = [
            "div.wprm-recipe-container",
            "div.tasty-recipes",
            "div.mv-create-card",
            "div.recipe-card",
            "div.recipe-content",
            "article",
            "main",
            ".post-content",
        ]
        target_content = None
        for selector in selectors:
            found = soup.select_one(selector)
            if found:
                self.emit_step(
                    "fetch_recipe", "in_progress", f"Recipe container found: {selector}"
                )
                target_content = found
                break

        if not target_content:
            target_content = soup.body

        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.body_width = 0
        markdown_content = h.handle(str(target_content))
        logger.info(
            f"Recipe fetched successfully, content length: {len(markdown_content)} chars"
        )
        return markdown_content

    def run(self, recipe_url: str):
        logger.info(f"Starting import process for: {recipe_url}")
        self.emit_step("fetch_recipe", "in_progress", "Starting import process...")

        try:
            markdown_content = self.fetch_recipe_from_url(recipe_url)
            self.emit_step("fetch_recipe", "completed")
            logger.info("Recipe fetched successfully")
        except Exception as e:
            self.emit_step("fetch_recipe", "failed", f"Error fetching URL: {e}")
            logger.error(f"Failed to fetch recipe: {e}")
            return

        self.emit_step(
            "extract_ingredients",
            "in_progress",
            "Extracting ingredients and metadata...",
        )
        try:
            ingredients_data = self.extract_metadata_and_ingredients(markdown_content)
            self.emit_step("extract_ingredients", "completed")
            logger.info(
                f"Extracted {len(ingredients_data.get('ingredients', []))} ingredients"
            )
        except Exception as e:
            self.emit_step(
                "extract_ingredients", "failed", f"Ingredients extraction failed: {e}"
            )
            logger.error(f"Ingredients extraction failed: {e}")
            return

        self.emit_step(
            "analyze_instructions", "in_progress", "Analyzing instructions..."
        )
        try:
            steps_data = self.extract_steps(markdown_content)
            self.emit_step("analyze_instructions", "completed")
            logger.info(f"Extracted {len(steps_data.get('steps', []))} steps")
        except Exception as e:
            self.emit_step(
                "analyze_instructions", "failed", f"Steps extraction failed: {e}"
            )
            logger.error(f"Steps extraction failed: {e}")
            return

        full_recipe_data = {**ingredients_data, **steps_data}
        recipe_title = full_recipe_data.get("title", "recipe")
        logger.info(f"Saving recipe '{recipe_title}' to Cookidoo")
        self.emit_step(
            "save_to_collection",
            "in_progress",
            f"Saving '{recipe_title}' to Cookidoo...",
        )

        try:
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=False)
                page = browser.new_page(viewport={"width": 1400, "height": 800})
                self.login_cookidoo(
                    os.getenv("COOKIDOO_USERNAME") or "",
                    os.getenv("COOKIDOO_PASSWORD") or "",
                    page,
                )
                self.create_recipe(page, full_recipe_data)
                browser.close()
                logger.info(f"Recipe '{recipe_title}' saved successfully")
        except Exception as e:
            self.emit_step(
                "save_to_collection", "failed", f"Failed to save recipe: {e}"
            )
            logger.error(f"Failed to save recipe: {e}")
            return

        logger.info(f"Import completed successfully for: {recipe_url}")
        self.status_callback({"event": "done"})
