from playwright.sync_api import sync_playwright, Page
import dotenv
import os


dotenv.load_dotenv()

def login_cookidoo(username: str, password: str, page: Page) -> None:
    
    # check if we are already logged in
    if page.locator("a[class*='logout']").count() > 0:
        print("Already logged in.")
        return

    page.goto("https://cookidoo.es/")

    # reject cookies
    page.locator("button#onetrust-reject-all-handler").click()

    # click on a link with a class that contains 'login'
    page.locator("a[class*='login']").click()

    # look for the input with id username and fill it
    page.locator("input#username").fill(username)
    page.locator("input#password").fill(password)
    page.locator("button#login-submit-btn").click()
    print("Login process completed successfully.")

def create_recipe(page: Page, recipe_title: str, prep_time_hours: str, prep_time_minutes: str, total_time_hours: str, total_time_minutes: str, ingredientsArray: list, stepsArray: list) -> None:
    print("navigating to the create a new recipe page...")
    # navigate to the create a new recipe page
    page.goto("https://cookidoo.es/created-recipes")
    page.wait_for_load_state("networkidle")
    # click on the button to create a new recipe
    page.locator("#floating-button").click()
    page.locator("button#create-button").click()
    page.locator("input#recipe-title").fill(recipe_title)
    page.locator("button[class*='button--primary']").nth(1).click()

    page.locator("div.cr-recipe-settings-tiles__item.cr-recipe-settings-tiles__item--empty").first.click()
    page.locator("input[aria-describedby='prepTime-hours-validation']").fill(prep_time_hours)
    page.locator("input[aria-describedby='prepTime-minutes-validation']").fill(prep_time_minutes)

    page.locator("button#totalTime").first.click()
    page.locator("input[aria-describedby='totalTime-hours-validation']").fill(total_time_hours)
    page.locator("input[aria-describedby='totalTime-minutes-validation']").fill(total_time_minutes)

    page.locator("button[action='confirm']").first.click()

    page.locator("a.button--secondary").first.click()
    page.wait_for_load_state("networkidle")
    page.locator("button#add-steps").click()

    print("New recipe creation initiated.")

    print ("Adding steps...")

    for index, step in enumerate(stepsArray):
        add_step(page, step["description"], step["minutes"], step["seconds"], step["temperature"], step["speed"], step["direction"], index)

    print("All steps added. Adding ingredients...")

    for index, ingredient in enumerate(ingredientsArray):
        add_ingredient(page, ingredient["name"], ingredient["quantity"], ingredient["unit"], index)
    # deselect the last ingredient input field to avoid issues

    print("Recipe creation completed. saving the recipe...")
    page.wait_for_timeout(1000)
    page.locator("a.button--primary.cr-visible-on-desktop.cr-edit-tabs__confirm-button:visible").first.click()
    page.wait_for_timeout(1000)
    print("Recipe saved successfully.")


def add_ingredient(page: Page, ingredient_name: str, quantity: str, unit: str, item_index: int) -> None:
    ingredient_str = f"{ingredient_name} {quantity} {unit}"
    # find elements inside div #ingredients-tab
    input = page.locator("div#ingredients-tab").locator(f"cr-text-field[index='{item_index}'][contenteditable='true']")
    input.type(ingredient_str)
    input.press("Enter")
    input.evaluate("(el) => el.dispatchEvent(new Event('input', { bubbles: true }))", input)
    input.evaluate("el => el.blur()")

    print(f"Added ingredient: {ingredient_name}, Quantity: {quantity} {unit}")

def add_step(page: Page, description: str, minutes: str, seconds: str, temperature: str, speed: str, direction: str, step_index: int) -> None:
    # Open dropdown for step options
    page.locator("div#preparation-steps-tab").locator(f"cr-text-field[index='{step_index}'][contenteditable='true']").fill(description)
    page.locator("div#preparation-steps-tab").locator("span.icon--speed:visible").first.click()

    # Set minutes and seconds
    page.locator(f"input[aria-describedby='minutes']").fill(minutes)
    page.locator(f"input[aria-describedby='seconds']").fill(seconds)

    # Set temperature
    page.locator("cr-tts-temperature").locator("button[aria-controls='setting-panel']").click()
    page.locator(f"label[for='temperature-radio-{temperature}']").click()

    # Set speed and direction
    page.locator("cr-tts-speed").locator("button[aria-controls='setting-panel']").click()
    page.locator(f"label[for='direction-radio-{direction}']").click()
    page.locator(f"label[for='speed-radio-{speed}']").click()

    # Save the step
    page.locator("div#preparation-steps-tab").locator("button.cr-popover-modal__save.button--icon.button--primary").first.click()
    page.locator("div#preparation-steps-tab").locator("button[class*='cr-manage-list__add-button']").first.click()
    print(f"Added step: {description}, Time: {minutes}m {seconds}s, Temp: {temperature}, Speed: {speed}, Direction: {direction}")

def main() -> None:
    print("Starting browser test...")
    # create a firefox browser instance
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)
        page = browser.new_page(viewport={"width": 1400, "height": 800})
        print("Navigating to Cookidoo...")
        # call the login function with the
        login_cookidoo(os.getenv("COOKIDOO_USERNAME"), os.getenv("COOKIDOO_PASSWORD"), page)
        create_recipe(page, "Test Recipe", "0", "30", "1", "0", [
            {"name": "Tomato", "quantity": "2", "unit": "pcs"},
            {"name": "Salt", "quantity": "1", "unit": "tsp"},
            {"name": "Olive Oil", "quantity": "2", "unit": "tbsp"}
        ], [
            {"description": "Step 1", "minutes": "5", "seconds": "30", "temperature": "100", "speed": "3", "direction": "CCW"},
            {"description": "Step 1", "minutes": "5", "seconds": "30", "temperature": "100", "speed": "3", "direction": "CW"},
            {"description": "Step 2", "minutes": "10", "seconds": "45", "temperature": "120", "speed": "1", "direction": "CCW"}
        ])

        browser.close()


main()