import logging
import re
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

API_TOKEN = os.getenv("API_TOKEN")  # Получаем токен
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Замени на свой Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Функция для загрузки данных из файла
def load_data():
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

# Функция для сохранения данных в файл
def save_data(data):
    with open("data.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

# Загружаем данные при запуске бота
categories = load_data()

# Хранилище товаров
if not categories:
    categories = {
        "t-shirts": {
            "name": "👕 Футболки",
            "products": [
                {
                    "name": "Футболка белая",
                    "price": 1000,
                    "description": "Мягкая и удобная футболка.",
                    "photo_path": "images/t-shirt1.jpg"
                },
                {
                    "name": "Футболка черная",
                    "price": 1200,
                    "description": "Стильная черная футболка.",
                    "photo_path": "images/t-shirt2.jpg"
                }
            ]
        },
        "jeans": {
            "name": "👖 Джинсы",
            "products": [
                {
                    "name": "Джинсы синие",
                    "price": 2000,
                    "description": "Стильные синие джинсы.",
                    "photo_path": "images/jeans1.jpg"
                },
                {
                    "name": "Джинсы черные",
                    "price": 2200,
                    "description": "Стильные черные джинсы.",
                    "photo_path": "images/jeans2.jpg"
                }
            ]
        },
        "shorts": {
            "name": "🩳 Шорты",
            "products": [
                {
                    "name": "Шорты спортивные",
                    "price": 1500,
                    "description": "Удобные спортивные шорты.",
                    "photo_path": "images/shorts1.jpg"
                },
                {
                    "name": "Шорты джинсовые",
                    "price": 1800,
                    "description": "Стильные джинсовые шорты.",
                    "photo_path": "images/shorts2.jpg"
                }
            ]
        }
    }
    save_data(categories)  # Сохраняем стандартные данные в файл

user_carts = {}

# Главное меню
def get_main_kb():
    buttons = [[KeyboardButton(text=category["name"])] for category in categories.values()]
    buttons.append([KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="📦 Сделать заказ")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

# Клавиатура для выбора товаров в категории
def get_products_kb(category_key: str):
    products = categories[category_key]["products"]
    buttons = [[KeyboardButton(text=product["name"])] for product in products]
    buttons.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

class OrderForm(StatesGroup):
    name = State()
    phone = State()
    address = State()
    comment = State()

class QuantityForm(StatesGroup):
    quantity = State()

class AddProductForm(StatesGroup):
    category = State()
    name = State()
    price = State()
    description = State()
    photo = State()

    # Клавиатура добавления в корзину
def get_add_to_cart_kb(category_key: str, product_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить в корзину 🛍️", callback_data=f"add_{category_key}_{product_name}")]
    ])

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("👋 Добро пожаловать в наш магазин!\nВыберите категорию:", reply_markup=get_main_kb())

@dp.message(lambda message: message.text in [category["name"] for category in categories.values()])
async def handle_category_selection(message: types.Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором и находится ли он в состоянии добавления товара
    if message.from_user.id == ADMIN_ID and await state.get_state() == AddProductForm.category:
        # Если это администратор и он выбирает категорию для добавления товара
        category_key = next((key for key, category in categories.items() if category["name"] == message.text), None)
        if not category_key:
            await message.answer("❌ Категория не найдена, попробуйте снова.")
            return

        await state.update_data(category=category_key)
        await state.set_state(AddProductForm.name)
        await message.answer("📝 Введите **название товара**:")
    else:
        # Если это обычный пользователь, показываем товары в категории
        category_key = next((key for key, category in categories.items() if category["name"] == message.text), None)
        if category_key:
            await message.answer(f"📦 Товары в категории {categories[category_key]['name']}:")

            for product in categories[category_key]["products"]:
                photo = FSInputFile(product["photo_path"])
                await message.answer_photo(
                    photo=photo,
                    caption=f"{product['name']}\n{product['description']}\n💰 Цена: {product['price']} руб.",
                    reply_markup=get_add_to_cart_kb(category_key, product['name'])
                )

@dp.message(lambda message: any(product["name"] == message.text for category in categories.values() for product in category["products"]))
async def show_product(message: types.Message):
    for category_key, category in categories.items():
        for product in category["products"]:
            if product["name"] == message.text:
                photo = FSInputFile(product["photo_path"])
                await message.answer_photo(
                    photo=photo,
                    caption=f"{product['name']}\n{product['description']}\nЦена: {product['price']} руб.",
                    reply_markup=get_add_to_cart_kb(category_key, product['name'])
                )
                return

@dp.callback_query(lambda query: query.data.startswith("add_"))
async def add_to_cart(query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из callback_data
    data = query.data.split("_")
    category_key = data[1]
    product_name = data[2] if len(data) > 2 else None

    logger.info(f"Category key: {category_key}, Product name: {product_name}")

    # Сохраняем категорию и название товара в состоянии
    await state.update_data(category_key=category_key, product_name=product_name)
    await state.set_state(QuantityForm.quantity)
    await query.message.answer("📝 Введите количество товара:")

@dp.message(QuantityForm.quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное количество (целое число больше 0).")
        return

    data = await state.get_data()
    category_key = data["category_key"]
    product_name = data["product_name"]  # Используем сохранённое название товара
    user_id = message.from_user.id

    if user_id not in user_carts:
        user_carts[user_id] = []

    # Находим товар в категории
    product = next((product for product in categories[category_key]["products"] if product["name"] == product_name), None)
    if product:
        user_carts[user_id].append({
            "product": product,
            "quantity": quantity
        })
        await message.answer(f"✅ {product['name']} (x{quantity}) добавлен в корзину!")
    else:
        await message.answer("❌ Товар не найден.")

    await state.clear()

@dp.message(lambda message: message.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    cart_items = user_carts.get(user_id, [])
    if not cart_items:
        await message.answer("🛍️ Ваша корзина пуста.")
        return

    total_price = sum(item["product"]["price"] * item["quantity"] for item in cart_items)
    cart_text = "🛒 **Ваша корзина:**\n" + "\n".join(
        f"🔹 {item['product']['name']} (x{item['quantity']}) - {item['product']['price'] * item['quantity']} руб."
        for item in cart_items
    )
    
    await message.answer(f"{cart_text}\n💰 **Общая сумма:** {total_price} руб.")

@dp.message(lambda message: message.text == "📦 Сделать заказ")
async def start_order(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cart_items = user_carts.get(user_id, [])
    if not cart_items:
        await message.answer("🛍️ Ваша корзина пуста.")
        return

    await state.set_state(OrderForm.name)
    await message.answer("📝 Введите ваше **ФИО**:")

@dp.message(OrderForm.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(OrderForm.phone)
    await message.answer("📞 Введите ваш **номер телефона**:")

# Валидация номера телефона для Беларуси (менее строгая)
def is_valid_belarus_phone(phone: str) -> bool:
    # Удаляем все нецифровые символы
    cleaned_phone = re.sub(r"[^0-9]", "", phone)
    
    # Проверяем, что номер начинается с 375, 80 или 29 и имеет правильную длину
    if cleaned_phone.startswith("375") and len(cleaned_phone) == 12:
        return True
    elif cleaned_phone.startswith("80") and len(cleaned_phone) == 11:
        return True
    elif cleaned_phone.startswith("29") and len(cleaned_phone) == 9:
        return True
    return False

@dp.message(OrderForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text
    if not is_valid_belarus_phone(phone):
        await message.answer("❌ Некорректный формат номера телефона. Пожалуйста, введите номер еще раз.")
        return

    # Приводим номер к стандартному формату +375 (XX) XXX-XX-XX
    cleaned_phone = re.sub(r"[^0-9]", "", phone)
    if cleaned_phone.startswith("80"):
        cleaned_phone = "375" + cleaned_phone[2:]
    elif cleaned_phone.startswith("29"):
        cleaned_phone = "375" + cleaned_phone

    formatted_phone = f"+375 ({cleaned_phone[3:5]}) {cleaned_phone[5:8]}-{cleaned_phone[8:10]}-{cleaned_phone[10:]}"
    await state.update_data(phone=formatted_phone)
    await state.set_state(OrderForm.address)
    await message.answer("🏡 Введите ваш **адрес доставки**:")

@dp.message(OrderForm.address)
async def process_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(OrderForm.comment)
    await message.answer("✏️ Добавьте **комментарий** (или отправьте -, если без комментария):")

@dp.message(OrderForm.comment)
async def process_comment(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cart_items = user_carts.get(user_id, [])
    data = await state.get_data()
    comment = message.text if message.text != "-" else "Без комментария"

    order_text = (f"🛍️ **Новый заказ!**\n👤 ФИО: {data['name']}\n📞 Телефон: {data['phone']}\n"
                  f"🏡 Адрес: {data['address']}\n💬 Комментарий: {comment}\n\n"
                  f"**Товары:**\n" + "\n".join(
                      f"🔹 {item['product']['name']} (x{item['quantity']}) - {item['product']['price'] * item['quantity']} руб."
                      for item in cart_items
                  ) + f"\n💰 **Общая сумма:** {sum(item['product']['price'] * item['quantity'] for item in cart_items)} руб.")

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="confirm_order")]
    ])
    
    await bot.send_message(ADMIN_ID, order_text, reply_markup=confirm_kb)
    await message.answer("📩 **Ваш заказ отправлен администратору!**")
    await state.clear()

@dp.callback_query(lambda query: query.data == "confirm_order")
async def confirm_order(query: types.CallbackQuery):
    await query.message.edit_text(query.message.text + "\n✅ **Заказ подтвержден!**")
    await query.answer("✅ Заказ подтвержден!")

# Команда для администратора: добавить товар
@dp.message(Command("add_product"))
async def start_add_product(message: types.Message, state: FSMContext):
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    # Создаем клавиатуру с категориями + кнопка "Создать новую категорию"
    buttons = [[KeyboardButton(text=category["name"])] for category in categories.values()]
    buttons.append([KeyboardButton(text="➕ Создать новую категорию")])
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

    await state.set_state(AddProductForm.category)
    await message.answer("📂 Выберите категорию для нового товара или создайте новую:", reply_markup=kb)

@dp.message(AddProductForm.category)
async def handle_category_selection(message: types.Message, state: FSMContext):
    data = await state.get_data()

    # Если мы ожидаем ввод новой категории
    if data.get("awaiting_new_category"):
        # Создаем новую категорию
        new_category_key = message.text.lower().replace(" ", "_")
        categories[new_category_key] = {
            "name": message.text,
            "products": []
        }

        await state.update_data(category=new_category_key, awaiting_new_category=False)
        await state.set_state(AddProductForm.name)
        await message.answer(f"✅ Категория **{message.text}** создана!\nТеперь введите **название товара**:")
        return

    # Если выбрано "Создать новую категорию"
    if message.text == "➕ Создать новую категорию":
        await message.answer("📝 Введите название новой категории:")
        await state.update_data(awaiting_new_category=True)  # Устанавливаем флаг
        return

    # Если выбрана существующая категория
    category_key = next((key for key, category in categories.items() if category["name"] == message.text), None)
    if not category_key:
        await message.answer("❌ Категория не найдена, попробуйте снова.")
        return

    await state.update_data(category=category_key)
    await state.set_state(AddProductForm.name)
    await message.answer("📝 Введите **название товара**:")
    
@dp.message(AddProductForm.name)
async def process_product_name(message: types.Message, state: FSMContext):
    # Сохраняем название товара
    await state.update_data(name=message.text)
    # Переводим бота в состояние ввода цены
    await state.set_state(AddProductForm.price)
    await message.answer("💰 Введите **цену товара** (в рублях):")

@dp.message(AddProductForm.price)
async def process_product_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную цену (целое число больше 0).")
        return

    await state.update_data(price=price)
    await state.set_state(AddProductForm.description)
    await message.answer("📝 Введите **описание товара**:")

@dp.message(AddProductForm.description)
async def process_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProductForm.photo)
    await message.answer("📷 Отправьте **фото товара**:")

@dp.message(AddProductForm.photo)
async def process_product_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ Пожалуйста, отправьте фото.")
        return

    # Сохраняем фото
    photo_file = await bot.get_file(message.photo[-1].file_id)
    photo_path = f"images/{photo_file.file_id}.jpg"
    await bot.download_file(photo_file.file_path, photo_path)

    # Получаем данные из состояния
    data = await state.get_data()
    category = data.get("category")  # Берём категорию, выбранную пользователем

    if not category or category not in categories:
        await message.answer("❌ Ошибка: категория не найдена.")
        return

    # Добавляем товар в нужную категорию
    categories[category]["products"].append({
        "name": data["name"],
        "price": data["price"],
        "description": data["description"],
        "photo_path": photo_path
    })

    save_data(categories)  # Сохраняем стандартные данные в файл

    await message.answer(f"✅ Товар **{data['name']}** успешно добавлен в каталог в категорию {category}!", reply_markup=get_main_kb())
    await state.clear()

if __name__ == '__main__':
    dp.run_polling(bot)