from aiogram import Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils import create_excel

def register_manual_handlers(dp: Dispatcher, user_data: dict):
    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") is None 
        and message.text.isdigit()
    )
    async def get_number_of_sheets(message: types.Message):
        num_sheets = int(message.text)
        user_data[message.chat.id]["sheet_count"] = num_sheets
        user_data[message.chat.id]["step"] = "sheet_names"
        await message.answer("Введи названия листов через запятую:")

    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") == "sheet_names" 
        and "," in message.text
    )
    async def get_sheet_names_and_quantities(message: types.Message):
        sheets = [sheet.strip() for sheet in message.text.split(",")]
        user_data[message.chat.id]["sheets"] = sheets
        user_data[message.chat.id]["step"] = "maf_quantity"
        await ask_maf_quantity(message)

    async def ask_maf_quantity(message):
        sheets = user_data[message.chat.id]["sheets"]
        if "quantities" not in user_data[message.chat.id]:
            user_data[message.chat.id]["quantities"] = {}

        if len(user_data[message.chat.id]["quantities"]) < len(sheets):
            next_sheet = sheets[len(user_data[message.chat.id]["quantities"])]
            await message.answer(f"{next_sheet} в каком количестве?")
        else:
            user_data[message.chat.id]["current_sheet"] = sheets[0]
            user_data[message.chat.id]["step"] = "product_name"
            await message.answer(f"Начнем заполнять данные для листа: {sheets[0]}\nВведи название изделия:")

    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") == "maf_quantity" 
        and message.text.isdigit()
    )
    async def get_maf_quantity(message: types.Message):
        sheets = user_data[message.chat.id]["sheets"]
        maf_quantity = int(message.text)
        current_maf = sheets[len(user_data[message.chat.id]["quantities"])]
        user_data[message.chat.id]["quantities"][current_maf] = maf_quantity
        await ask_maf_quantity(message)

    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") == "product_name"
    )
    async def get_product_name(message: types.Message):
        current_sheet = user_data[message.chat.id]["current_sheet"]
        product_name = message.text
        if current_sheet not in user_data[message.chat.id]["products"]:
            user_data[message.chat.id]["products"][current_sheet] = []

        user_data[message.chat.id]["products"][current_sheet].append({
            "name": product_name,
            "quantity": 0,
            "unit": "",
            "price_per_unit": 0
        })
        user_data[message.chat.id]["step"] = "quantity"
        await message.answer("Введи количество:")

    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") == "quantity" 
        and message.text.isdigit()
    )
    async def get_product_quantity(message: types.Message):
        quantity = int(message.text)
        current_sheet = user_data[message.chat.id]["current_sheet"]
        user_data[message.chat.id]["products"][current_sheet][-1]["quantity"] = quantity
        user_data[message.chat.id]["step"] = "unit"
        
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ["м", "м²", "м³", "шт"]
        keyboard.add(*buttons)
        
        await message.answer("Введи единицы измерения (м, м², м³, шт):", reply_markup=keyboard)

    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") == "unit"
    )
    async def get_product_unit(message: types.Message):
        unit = message.text
        current_sheet = user_data[message.chat.id]["current_sheet"]
        user_data[message.chat.id]["products"][current_sheet][-1]["unit"] = unit
        user_data[message.chat.id]["step"] = "price"
        await message.answer("Введи цену за единицу изделия:", reply_markup=types.ReplyKeyboardRemove())

    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") == "price" 
        and message.text.replace('.', '', 1).isdigit()
    )
    async def get_product_price(message: types.Message):
        price = float(message.text)
        current_sheet = user_data[message.chat.id]["current_sheet"]
        user_data[message.chat.id]["products"][current_sheet][-1]["price_per_unit"] = price
        user_data[message.chat.id]["step"] = "next_product"
        await message.answer("Данные сохранены! Введи название следующего изделия или напиши 'далее' для перехода к следующему листу.")

    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'manual' 
        and user_data[message.chat.id].get("step") == "next_product"
    )
    async def process_next_product_or_sheet(message: types.Message):
        if message.text.lower() == 'далее':
            current_sheet = user_data[message.chat.id]["current_sheet"]
            sheets = user_data[message.chat.id]["sheets"]
            current_index = sheets.index(current_sheet)
            
            if current_index + 1 < len(sheets):
                next_sheet = sheets[current_index + 1]
                user_data[message.chat.id]["current_sheet"] = next_sheet
                user_data[message.chat.id]["step"] = "product_name"
                await message.answer(f"Переходим к следующему листу: {next_sheet}\nВведи название изделия:")
            else:
                await message.answer("Все данные введены! Сейчас сформирую Excel файл.")
                create_excel(message.chat.id, user_data)
                await message.answer_document(open(f"smeta_{message.chat.id}.xlsx", "rb"))
                user_data[message.chat.id].clear()
        else:
            current_sheet = user_data[message.chat.id]["current_sheet"]
            product_name = message.text
            user_data[message.chat.id]["products"][current_sheet].append({
                "name": product_name,
                "quantity": 0,
                "unit": "",
                "price_per_unit": 0
            })
            user_data[message.chat.id]["step"] = "quantity"
            await message.answer("Введи количество:")