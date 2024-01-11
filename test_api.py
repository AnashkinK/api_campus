import httpx
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
import asyncio
import redis
import json

app = Flask(__name__)
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

#Асинхронная функция для получения расписания по группе
async def fetch_schedule(group_number, selected_week_value):
    url = 'https://campus.syktsu.ru/schedule/group/'

    async with httpx.AsyncClient() as client:
        #Страница с расписанием группы и POST запрос на ввод номера группы
        response = await client.post(url, data={'num_group': group_number})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            weeks_select = soup.find('select', {'name': 'weeks'})
            if weeks_select:
                weeks_select.find('option', {'value': selected_week_value}).selected = True
                #POST запрос на выбор недели
                response = await client.post(url, data={'num_group': group_number, 'weeks': selected_week_value})
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    schedule_table = soup.find('table', {'class': 'schedule'})

                    if schedule_table:
                        selected_rows = []
                        columns = schedule_table.find_all(['th', 'td'])
                        row_data = [col.text.strip() for col in columns]
                        selected_rows.append(row_data)
                        #print(f"Row data: {row_data}")

                        return selected_rows
    return None
#Запрос расписание по преподавателю
async def teacher_schedule(teacher_fio, selected_week_value):
    url = 'https://campus.syktsu.ru/schedule/teacher/'

    async with httpx.AsyncClient() as client:
        response = await client.post(url, data={'fio': teacher_fio})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            weeks_select = soup.find('select', {'name': 'weeks'})
            if weeks_select:
                weeks_select.find('option', {'value': selected_week_value}).selected = True

                response = await client.post(url, data={'fio': teacher_fio, 'weeks': selected_week_value})
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    schedule_table = soup.find('table', {'class': 'schedule'})

                    if schedule_table:
                        # all_rows = schedule_table.find_all('tr')

                        selected_rows = []
                        columns = schedule_table.find_all(['th', 'td'])
                        row_data = [col.text.strip() for col in columns]
                        selected_rows.append(row_data)
                        print(f"Row data: {row_data}")

                        return selected_rows
    return None

async def classroom_schedule(room, selected_week_value):
    url = 'https://campus.syktsu.ru/schedule/classroom/'

    async with httpx.AsyncClient() as client:
        response = await client.post(url, data={'num_aud': room})
        soup = BeautifulSoup(response.text, 'html.parser')

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            weeks_select = soup.find('select', {'name': 'weeks'})
            if weeks_select:
                #Выбор недели в списке
                weeks_select.find('option', {'value': selected_week_value}).selected = True #Поумолчанию в списке

                response = await client.post(url, data={'num_aud': room, 'weeks': selected_week_value})
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    schedule_table = soup.find('table', {'class': 'schedule'})

                    if schedule_table:
                        # all_rows = schedule_table.find_all('tr')

                        selected_rows = []
                        columns = schedule_table.find_all(['th', 'td'])
                        row_data = [col.text.strip() for col in columns]
                        selected_rows.append(row_data)
                        # print(f"Row data: {row_data}")

                        return selected_rows
    return None

async def schedule_teacher_async(teacher_fio, selected_week_value):
    key = f'schedule:{teacher_fio}:{selected_week_value}'
    cached_schedule = redis_client.get(key)

    if cached_schedule:
        return json.loads(cached_schedule)

    schedule_data = await teacher_schedule(teacher_fio, selected_week_value)

    if schedule_data:
        redis_client.set(key, json.dumps(schedule_data), ex=3600)  # Кэшируем на 1 час
        return schedule_data

    return None

async def schedule_group_async(group_number, selected_week_value):
    key = f'schedule:{group_number}:{selected_week_value}'
    cached_schedule = redis_client.get(key)

    if cached_schedule:
        return eval(cached_schedule)

    schedule_data = await fetch_schedule(group_number, selected_week_value)

    if schedule_data:
        redis_client.set(key, str(schedule_data), ex=3600)  # Кэшируем на 1 час
        return schedule_data

    return None

async def schedule_room_async(room_number, selected_week_value):
    key = f'schedule:{room_number}:{selected_week_value}'
    cached_schedule = redis_client.get(key)

    if cached_schedule:
        return eval(cached_schedule)

    schedule_data = await classroom_schedule(room_number, selected_week_value)

    if schedule_data:
        redis_client.set(key, str(schedule_data), ex=3600)  # Кэшируем на 1 час
        return schedule_data

    return None
#Обработчик запросов
@app.route('/api/schedule', methods=['GET']) # http://127.0.0.1:5000/api/schedule?group_number=1415-ИРо&selected_week_value=6_1415-ИРо
def get_group_schedule():
    group_number = request.args.get('group_number')
    selected_week_value = request.args.get('selected_week_value')

    if not group_number or not selected_week_value:
        return jsonify({'error': 'Неверные параметры'}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    schedule_data = loop.run_until_complete(schedule_group_async(group_number, selected_week_value))

    if schedule_data:
        return jsonify({'schedule': schedule_data})
    else:
        return jsonify({'error': 'Расписание не найдено'}), 404

@app.route('/api/teacher', methods=['GET']) # http://127.0.0.1:5000/api/teacher?teacher_fio=Кирпичёв&selected_week_value=3_Кирпичев Алексей Николаевич
def get_teacher_schedule():
    teacher_fio = request.args.get('teacher_fio')
    selected_week_value = request.args.get('selected_week_value')

    if not teacher_fio or not selected_week_value:
        return jsonify({'error': 'Неверные параметры'}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    schedule_data = loop.run_until_complete(schedule_teacher_async(teacher_fio, selected_week_value))

    if schedule_data:
        return jsonify({'schedule': schedule_data})
    else:
        return jsonify({'error': 'Расписание не найдено'}), 404

@app.route('/api/classroom', methods=['GET']) # http://127.0.0.1:5000/api/classroom?num_aud=251&selected_week_value=20_251/1
def get_room_schedule():
    num_aud = request.args.get('num_aud')
    selected_week_value = request.args.get('selected_week_value')

    if not num_aud or not selected_week_value:
        return jsonify({'error': 'Неверные параметры'}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    schedule_data = loop.run_until_complete(schedule_room_async(num_aud, selected_week_value))

    if schedule_data:
        return jsonify({'schedule': schedule_data})
    else:
        return jsonify({'error': 'Расписание не найдено'}), 404
#Изолирование кода
if __name__ == "__main__":
    app.run(debug=True) #режим откладки flask слушает напрямую запросы