import csv
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

STATIONS = [
    {"name": "moro", "url": "https://www.weatherlink.com/embeddablePage/show/087a0cad8b934e1d9e20ff9118220dba/summary"},
    {"name": "apaseoalto", "url": "https://www.weatherlink.com/embeddablePage/show/3f51dabcd7194bfeb01298ee07821187/summary"},
    {"name": "atarjea", "url": "https://www.weatherlink.com/embeddablePage/show/32dfb492a35b4d20b3051c39027c9200/summary", "station_title": "Estación Atarjea2"},
    {"name": "doctormora", "url": "https://www.weatherlink.com/embeddablePage/show/5c9b412614a446ae92160b386ea3c6d5/summary"},
    {"name": "villalpando", "url": "https://www.weatherlink.com/embeddablePage/show/e7ddbcf7d26e4ef981567ca6a4c15d56/summary"},
    {"name": "silaocepc44", "url": "https://www.weatherlink.com/embeddablePage/show/63bacf5cbc374ee18447fefa46c52219/summary"},
    #{"name": "sanfelipe", "url": "https://www.weatherlink.com/embeddablePage/show/882d88b568cc47b396cdd549199b4abd/summary"},
    {"name": "tierrablanca", "url": "https://www.weatherlink.com/embeddablePage/show/76e1ddc54f02479bae9ea77567a5770b/summary"},
    {"name": "xichu", "url": "https://www.weatherlink.com/embeddablePage/show/127dc157f6ff4de79b2ae57c2fa909d6/summary"},
    {"name": "elalamo", "url": "https://www.weatherlink.com/embeddablePage/show/db27336876234ff68a99e76fb1dca088/summary"},
    {"name": "arreguin", "url": "https://www.weatherlink.com/embeddablePage/show/3a7ed8dc9ac44a648bd9e5489f3b456b/summary"},
    {"name": "capulines", "url": "https://www.weatherlink.com/embeddablePage/show/174b9645230d44bc96612f871ec4f7be/summary"},
    {"name": "pccelaya", "url": "https://www.weatherlink.com/embeddablePage/show/500c85a0d3224b44b9b6aa47a576d18f/summary"},
    {"name": "enmsi", "url": "https://www.weatherlink.com/embeddablePage/show/52bae29e361f43afb732162476626a10/summary"},
    {"name": "paxtle", "url": "https://www.wunderground.com/dashboard/pws/ISILAO10", "source": "wunderground"},
    {"name": "pcsilao", "url": "https://www.wunderground.com/dashboard/pws/ISILAO9", "source": "wunderground"},
    #{"name": "cubilete", "url": "https://www.wunderground.com/dashboard/pws/ISILAO11", "source": "wunderground"}
]
CSV_FILENAME = "Rdata2.csv"


def parse_wind_speed(value_text, unit=None):
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value_text)
    if not match:
        raise ValueError(f"No se encontró velocidad del viento en: {value_text}")

    speed = float(match.group().replace(",", "."))
    unit_text = (unit or value_text).strip().lower()
    if unit_text == "e" or re.search(r"\b(mph|mi/h)\b", unit_text):
        speed *= 1.60934
    elif unit_text == "m" or re.search(r"\b(km/h|kph)\b", unit_text):
        pass
    elif re.search(r"\b(m/s|mps)\b", unit_text):
        speed *= 3.6
    elif re.search(r"\b(kn|knot|knots)\b", unit_text):
        speed *= 1.852
    elif not unit:
        speed *= 1
    else:
        raise ValueError(f"Unidad no reconocida para velocidad del viento: {unit}")
    return speed


def scrape_weatherlink_wind(driver):
    wind_speed = None
    wind_direction = None
    average_speed_labels = driver.find_elements(
        By.CSS_SELECTOR,
        "td[data-l10n-id='sensor_wind_avg_spd']",
    )
    if average_speed_labels:
        try:
            value_cell = average_speed_labels[0].find_element(
                By.XPATH,
                "./following-sibling::td[contains(concat(' ', normalize-space(@class), ' '), ' col-2 ')][1]",
            )
            wind_speed = parse_wind_speed(" ".join(value_cell.text.split()))
        except (
            NoSuchElementException,
            ValueError,
            WebDriverException,
        ):
            pass

    labels = driver.find_elements(
        By.CSS_SELECTOR,
        ".summary-block td.col-3",
    )

    for label in labels:
        label_text = " ".join(label.text.casefold().split())
        if "viento" not in label_text and "wind" not in label_text:
            continue

        value_cell = label.find_element(
            By.XPATH,
            "./following-sibling::td[contains(concat(' ', normalize-space(@class), ' '), ' col-2 ')][1]",
        )
        value_text = " ".join(value_cell.text.split())
        if any(word in label_text for word in ("dirección", "direccion", "direction", "rumbo")):
            wind_direction = value_text
        elif (
            wind_speed is None
            and any(word in label_text for word in ("promedio", "average", "avg"))
            and any(word in label_text for word in ("velocidad", "speed"))
        ):
            try:
                wind_speed = parse_wind_speed(value_text)
            except ValueError:
                pass

    return wind_speed, wind_direction


def scrape_wunderground_wind(driver, station_id, conditions_selector):
    wind_widget_selector = f"wind-widget-view[data-pws-id='{station_id}']"
    wind_widgets = driver.find_elements(By.CSS_SELECTOR, wind_widget_selector)
    wind_direction = ""
    wind_speed = None
    speed_text = ""

    if wind_widgets:
        wind_widget = wind_widgets[0]
        speed_text = wind_widget.get_attribute("data-main-value") or ""
        speed_unit = wind_widget.get_attribute("data-unit")
        wind_direction = (
            wind_widget.get_attribute("data-wind-direction")
            or wind_widget.get_attribute("data-direction")
            or ""
        ).strip()
        try:
            wind_speed = parse_wind_speed(speed_text, speed_unit)
        except ValueError:
            pass
    else:
        try:
            current_conditions = driver.find_element(By.XPATH, conditions_selector)
            speed_element = current_conditions.find_element(
                By.CSS_SELECTOR, ".wu-unit-speed .wu-value-to"
            )
            speed_text = speed_element.find_element(By.XPATH, "..").text.strip()
            wind_speed = parse_wind_speed(speed_text)
        except (NoSuchElementException, ValueError, WebDriverException):
            pass

    if not wind_direction:
        direction_elements = driver.find_elements(
            By.CSS_SELECTOR, ".wu-unit-dir .wu-value-to"
        )
        wind_direction = direction_elements[0].text.strip() if direction_elements else ""
    if not wind_direction:
        direction_elements = driver.find_elements(
            By.CSS_SELECTOR, ".wind-dial__container"
        )
        wind_direction = direction_elements[0].text.strip() if direction_elements else ""
    if not wind_direction:
        direction_match = re.search(
            r"\b(NNE|ENE|ESE|SSE|SSW|WSW|WNW|NNW|N|NE|E|SE|S|SW|W|NW)\b",
            speed_text,
            re.IGNORECASE,
        )
        if direction_match:
            wind_direction = direction_match.group().upper()

    return wind_speed, wind_direction


def get_optional_weather_value(station_name, field_name, getter):
    try:
        return getter()
    except (
        AttributeError,
        IndexError,
        NoSuchElementException,
        TimeoutException,
        TypeError,
        ValueError,
        WebDriverException,
    ) as e:
        print(f"Dato no disponible para {station_name} ({field_name}): {e}")
        return None


def scrape_weather(station_url, station_name, source="weatherlink", station_title=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    weather_data = {
        "station": station_name,
        "temp": "--",
        "rain": "--",
        "wind_speed": "--",
        "wind_direction": "--",
    }

    try:
        driver.get(station_url)
        wait = WebDriverWait(driver, 45 if source == "wunderground" else 15)

        if source == "wunderground":
            station_id = station_url.rstrip("/").rsplit("/", 1)[-1]
            temp_widget_selector = f"temp-widget-view[data-pws-id='{station_id}']"
            rain_widget_selector = f"rain-widget-view[data-pws-id='{station_id}']"
            conditions_selector = (
                "//div[contains(@class,'module__container')]"
                "[.//div[contains(@class,'module__header') and normalize-space()='Current Conditions']]"
            )

            page_version = wait.until(lambda current_driver:
                "new" if (
                    current_driver.find_elements(By.CSS_SELECTOR, temp_widget_selector)
                    or current_driver.find_elements(By.CSS_SELECTOR, rain_widget_selector)
                )
                else "classic" if current_driver.find_elements(By.XPATH, conditions_selector)
                else False,
                "Tiempo agotado esperando a que se cargue la página de Weather Underground",
            )

            if page_version == "new":
                def scrape_temperature():
                    temp_widget = driver.find_element(By.CSS_SELECTOR, temp_widget_selector)
                    value = float(temp_widget.get_attribute("data-main-value"))
                    unit = temp_widget.get_attribute("data-unit")
                    if unit == "e":
                        value = (value - 32) * 5 / 9
                    elif unit != "m":
                        raise ValueError(f"Unidad no reconocida para temperatura: {unit}")
                    return value

                def scrape_rain():
                    rain_widget = driver.find_element(By.CSS_SELECTOR, rain_widget_selector)
                    value = float(rain_widget.get_attribute("data-precip-rate"))
                    unit = rain_widget.get_attribute("data-unit")
                    if unit == "e":
                        value *= 25.4
                    elif unit != "m":
                        raise ValueError(f"Unidad no reconocida para precipitación: {unit}")
                    return value

                temp_value = get_optional_weather_value(
                    station_name, "temperatura", scrape_temperature
                )
                rain_value = get_optional_weather_value(
                    station_name, "precipitación", scrape_rain
                )
            else:
                current_conditions = driver.find_element(By.XPATH, conditions_selector)

                def scrape_temperature():
                    temp_element = wait.until(lambda _: current_conditions.find_element(
                        By.CSS_SELECTOR, ".conditions-temp .wu-value-to"
                    ), "Tiempo agotado esperando a que se cargue la temperatura de Weather Underground")
                    temp_text = temp_element.find_element(By.XPATH, "..").text
                    value = float(temp_element.text.strip().split()[0])
                    if "°F" in temp_text:
                        value = (value - 32) * 5 / 9
                    elif "°C" not in temp_text:
                        raise ValueError(f"Unidad no reconocida para temperatura: {temp_text}")
                    return value

                def scrape_rain():
                    rain_element = wait.until(lambda _: current_conditions.find_element(
                        By.CSS_SELECTOR, ".wu-unit-rainRate .wu-value-to"
                    ), "Tiempo agotado esperando a que se cargue la tasa de precipitación de Weather Underground")
                    rain_text = rain_element.find_element(By.XPATH, "..").text
                    value = float(rain_element.text.strip().split()[0])
                    if "in/hr" in rain_text:
                        value *= 25.4
                    elif "mm/hr" not in rain_text:
                        raise ValueError(f"Unidad no reconocida para precipitación: {rain_text}")
                    return value

                temp_value = get_optional_weather_value(
                    station_name, "temperatura", scrape_temperature
                )
                rain_value = get_optional_weather_value(
                    station_name, "precipitación", scrape_rain
                )

            wind_data = get_optional_weather_value(
                station_name,
                "viento",
                lambda: scrape_wunderground_wind(
                    driver, station_id, conditions_selector
                ),
            )
        else:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "summary-block")))
            time.sleep(1)
            station_section = driver.find_element(By.ID, "currentCond")
            wait.until(
                lambda _: station_section.find_elements(
                    By.CSS_SELECTOR, ".summary-block"
                ),
                "Tiempo agotado esperando al resumen de la estación WeatherLink activa",
            )
            if station_title:
                section_title = station_section.find_element(
                    By.CSS_SELECTOR, ".section-header-tr td"
                ).text.strip()
                if section_title != station_title:
                    raise ValueError(
                        f"Estación WeatherLink incorrecta: se esperaba "
                        f"'{station_title}' y se encontró '{section_title}'"
                    )

            def scrape_temperature():
                temp_label = station_section.find_element(
                    By.XPATH,
                    ".//td[contains(concat(' ', normalize-space(@class), ' '), ' col-3 ') "
                    "and (normalize-space()='Temperatura' or normalize-space()='Temperature')]",
                )
                temp_cell = temp_label.find_element(By.XPATH, "./following-sibling::td[@class='col-2'][1]")
                return float(temp_cell.text.strip().split()[0])

            def scrape_rain():
                rain_block = station_section.find_element(By.CLASS_NAME, "rain-block")
                wait.until(EC.visibility_of(rain_block))
                rain_row = rain_block.find_element(
                    By.XPATH, ".//tr[contains(@class,'data-row')][1]"
                )
                rain_cells = rain_row.find_elements(By.CLASS_NAME, "col-1")
                if not rain_cells:
                    raise ValueError("No se encontró datos de tasa de precipitación")
                return float(rain_cells[0].text.strip().split()[0])

            temp_value = get_optional_weather_value(
                station_name, "temperatura", scrape_temperature
            )
            rain_value = get_optional_weather_value(
                station_name, "precipitación", scrape_rain
            )
            wind_data = get_optional_weather_value(
                station_name,
                "viento",
                lambda: scrape_weatherlink_wind(station_section),
            )

        if temp_value is not None:
            weather_data["temp"] = round(temp_value, 1)
        if rain_value is not None:
            weather_data["rain"] = round(rain_value, 1)
        if wind_data is not None:
            wind_speed, wind_direction = wind_data
            if wind_speed is not None:
                weather_data["wind_speed"] = round(wind_speed, 1)
            else:
                print(f"Dato no disponible para {station_name} (velocidad del viento).")
            if wind_direction:
                weather_data["wind_direction"] = wind_direction
            else:
                print(f"Dato no disponible para {station_name} (dirección del viento).")

        print(
            f"Scraped: {station_name} | "
            f"{weather_data['temp']} °C | "
            f"Precipitación: "
            f"{weather_data['rain']} mm/h | "
            f"Viento: "
            f"{weather_data['wind_speed']} km/h "
            f"{weather_data['wind_direction']}"
        )

    except TimeoutException as e:
        print(f"Tiempo agotado {station_name}: {e}")
    except NoSuchElementException as e:
        print(f"Elemento no encontrado scraping {station_name}: {e}")
        try:
            summary = driver.find_element(By.CLASS_NAME, "summary-block")
            print("--- Summary block HTML snippet ---")
            print(summary.get_attribute("outerHTML")[:800])
        except Exception:
            pass
        try:
            rain = driver.find_element(By.CLASS_NAME, "rain-block")
            print("--- Rain block HTML snippet ---")
            print(rain.get_attribute("outerHTML")[:800])
        except Exception:
            pass
    except Exception as e:
        print(f"Error inesperado {station_name}: {e}")
    finally:
        try:
            driver.quit()
        except WebDriverException as e:
            print(f"No se pudo cerrar el navegador para {station_name}: {e}")

    return weather_data


def save_to_csv(data, filename=CSV_FILENAME):
    if not data:
        print("⚠ No hay datos para guardar.")
        return

    stations_by_name = {}
    try:
        with open(filename, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                station_name = row.get("station", "").strip()
                if station_name:
                    stations_by_name[station_name.lower()] = [
                        station_name,
                        row.get("temp", "--") or "--",
                        row.get("rain", "--") or "--",
                        row.get("wind_speed", "--") or "--",
                        row.get("wind_direction", "--") or "--",
                    ]
    except FileNotFoundError:
        pass

    station_name = data["station"].strip()
    station_key = station_name.lower()
    values = []
    for field in ("temp", "rain", "wind_speed", "wind_direction"):
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            value = "--"
        values.append(value)
    has_weather_data = any(
        value is not None and str(value).strip() not in ("", "--")
        for value in values
    )
    if has_weather_data:
        stations_by_name[station_key] = [station_name, *values]
    else:
        removed_station = stations_by_name.pop(station_key, None) is not None

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["station", "temp", "rain", "wind_speed", "wind_direction"])
        writer.writerows(stations_by_name.values())

    if has_weather_data:
        print(f"✅ Datos guardados en {filename}")
    elif removed_station:
        print(f"⚠ {station_name} eliminada de {filename}: no se obtuvo ningún dato.")
    else:
        print(f"⚠ {station_name}: sin datos; no hay una fila que eliminar en {filename}.")


if __name__ == "__main__":
    for station in STATIONS:
        data = scrape_weather(
            station["url"],
            station["name"],
            station.get("source", "weatherlink"),
            station.get("station_title"),
        )
        if data:
            save_to_csv(data)
