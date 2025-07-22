function updateFileLabel() {
    const input = document.getElementById('imageInput');
    const label = document.getElementById('fileLabel');
    if (input.files.length > 0) {
        label.textContent = input.files[0].name;
    } else {
        label.textContent = 'Выберите изображение или видео';
    }
}
async function processFile() {
    const file = document.getElementById('imageInput').files[0];
    if (!file) return;
    document.getElementById('resultBlock').innerHTML = '';
    document.getElementById('stats').innerText = '';
    const loader = document.createElement('div');
    loader.className = 'loader';
    document.getElementById('resultBlock').appendChild(loader);
    const formData = new FormData();
    formData.append('image', file);
    try {
        const response = await fetch('/process', { method: 'POST', body: formData });
        const data = await response.json();
        let resultBlock = document.getElementById('resultBlock');
        resultBlock.innerHTML = '';
        if (data.type === 'image') {
            resultBlock.innerHTML = `<img src="/static/result.jpg?${Date.now()}" alt="Результат">`;
        } else if (data.type === 'video') {
            resultBlock.innerHTML = `<video src="/static/result.mp4?${Date.now()}" controls></video>`;
        } else {
            resultBlock.innerHTML = '';
        }
        document.getElementById('stats').innerText = `Количество пицц: ${data.count}`;
    } catch (e) {
        document.getElementById('resultBlock').innerHTML = '<span style="color:#d35400;">Ошибка обработки файла</span>';
    }
} 