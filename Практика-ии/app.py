import os
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from ultralytics import YOLO
import cv2
import numpy as np
import sqlite3
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import openpyxl
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

STATIC_DIR = 'static'
RESULT_IMAGE = 'result.jpg'
RESULT_VIDEO = 'result.mp4'
DB_PATH = 'history.db'

# Регистрируем шрифт DejaVuSans для кириллицы
pdfmetrics.registerFont(TTFont('DejaVuSans', os.path.join(STATIC_DIR, 'DejaVuSans.ttf')))

app = Flask(__name__)
model = YOLO('yolov8n.pt')  # Загружаем модель

PIZZA_CLASS_ID = 53  # Класс пиццы в вашей модели

os.makedirs(STATIC_DIR, exist_ok=True)

def save_history(count, filetype, result_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS requests
                      (timestamp TEXT, count INTEGER, filetype TEXT, result_path TEXT)''')
    cursor.execute('INSERT INTO requests (timestamp, count, filetype, result_path) VALUES (?, ?, ?, ?)',
                   (datetime.now().isoformat(), count, filetype, result_path))
    conn.commit()
    conn.close()

def generate_reports():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, count, filetype, result_path FROM requests ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    # PDF
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    c.setFont('DejaVuSans', 16)
    c.drawString(40, height-40, 'Отчёт по обработке пицц')
    c.setFont('DejaVuSans', 10)
    y = height-70
    X_DATE = 40
    X_COUNT = 170
    X_TYPE = 250
    X_FILE = 370
    c.drawString(X_DATE, y, 'Дата и время')
    c.drawString(X_COUNT, y, 'Кол-во пицц ')
    c.drawString(X_TYPE, y, 'Тип')
    c.drawString(X_FILE, y, 'Файл')
    y -= 18
    for row in rows:
        c.drawString(X_DATE, y, str(row[0]))
        c.drawRightString(X_COUNT + 30, y, str(row[1]))  # числа справа
        c.drawString(X_TYPE, y, str(row[2]))
        c.drawString(X_FILE, y, str(row[3]))
        y -= 16
        if y < 40:
            c.showPage()
            y = height-40
    c.save()
    with open(os.path.join(STATIC_DIR, 'pizza_report.pdf'), 'wb') as f:
        f.write(pdf_buffer.getvalue())
    # Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'История'
    ws.append(['Дата и время', 'Кол-во пицц', 'Тип', 'Файл'])
    for row in rows:
        ws.append(list(row))
    wb.save(os.path.join(STATIC_DIR, 'pizza_report.xlsx'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_file():
    file = request.files['image']
    filename = file.filename.lower()
    ext = os.path.splitext(filename)[1]
    if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        # Обработка изображения
        img = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_COLOR)
        results = model(img)
        print('Class names:', results[0].names)
        boxes = results[0].boxes
        debug_info = []
        for box in boxes:
            class_id = int(box.cls.item())
            conf = float(box.conf.item())
            name = results[0].names[class_id]
            debug_info.append({'class_id': class_id, 'name': name, 'conf': conf})
        print('DETECTED BOXES:', debug_info)
        # Временно убираю фильтр по conf
        pizza_boxes = [box for box in boxes if int(box.cls.item()) == PIZZA_CLASS_ID]
        print('Pizza boxes count:', len(pizza_boxes))
        output_img = results[0].plot()
        result_path = os.path.join(STATIC_DIR, RESULT_IMAGE)
        cv2.imwrite(result_path, output_img)
        save_history(len(pizza_boxes), 'image', result_path)
        generate_reports()
        return jsonify({'count': len(pizza_boxes), 'type': 'image'})
    elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
        # Обработка видео
        temp_path = os.path.join(STATIC_DIR, 'temp_video'+ext)
        file.save(temp_path)
        cap = cv2.VideoCapture(temp_path)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_path = os.path.join(STATIC_DIR, RESULT_VIDEO)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
        max_pizzas = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            results = model(frame)
            boxes = results[0].boxes
            pizza_boxes = [box for box in boxes if int(box.cls.item()) == PIZZA_CLASS_ID and float(box.conf.item()) > 0.3]
            max_pizzas = max(max_pizzas, len(pizza_boxes))
            frame_out = results[0].plot()
            out.write(frame_out)
        cap.release()
        out.release()
        os.remove(temp_path)
        save_history(max_pizzas, 'video', out_path)
        generate_reports()
        return jsonify({'count': max_pizzas, 'type': 'video'})
    else:
        return jsonify({'error': 'Unsupported file type'}), 400

@app.route('/report/pdf')
def report_pdf():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, count, filetype, result_path FROM requests ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont('DejaVuSans', 16)
    c.drawString(40, height-40, 'Отчёт по обработке пицц')
    c.setFont('DejaVuSans', 10)
    y = height-70
    X_DATE = 40
    X_COUNT = 170
    X_TYPE = 250
    X_FILE = 370
    c.drawString(X_DATE, y, 'Дата и время')
    c.drawString(X_COUNT, y, 'Кол-во пицц ')
    c.drawString(X_TYPE, y, 'Тип')
    c.drawString(X_FILE, y, 'Файл')
    y -= 18
    for row in rows:
        c.drawString(X_DATE, y, str(row[0]))
        c.drawRightString(X_COUNT + 30, y, str(row[1]))  # числа справа
        c.drawString(X_TYPE, y, str(row[2]))
        c.drawString(X_FILE, y, str(row[3]))
        y -= 16
        if y < 40:
            c.showPage()
            y = height-40
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='pizza_report.pdf', mimetype='application/pdf')

@app.route('/report/excel')
def report_excel():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, count, filetype, result_path FROM requests ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'История'
    ws.append(['Дата и время', 'Кол-во пицц', 'Тип', 'Файл'])
    for row in rows:
        ws.append(list(row))
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='pizza_report.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True) 