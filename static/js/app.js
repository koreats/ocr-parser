let currentTemplate = 'claude';
let currentResult = null;

// 템플릿 선택
document.querySelectorAll('.template-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.template-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        currentTemplate = this.dataset.template;
        
        if (currentResult) {
            updatePromptDisplay(currentResult);
        }
    });
});

// 드래그 앤 드롭
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    
    const file = e.dataTransfer.files[0];
    if (file) {
        handleFileUpload(file);
    }
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFileUpload(file);
    }
});

// 파일 업로드 처리
async function handleFileUpload(file) {
    const validTypes = ['image/png', 'image/jpeg', 'application/pdf'];
    
    if (!validTypes.includes(file.type)) {
        showAlert('PNG, JPG, PDF 파일만 업로드 가능합니다.', 'error');
        return;
    }
    
    if (file.size > 50 * 1024 * 1024) {
        showAlert('파일 크기는 50MB 이하여야 합니다.', 'error');
        return;
    }
    
    uploadZone.classList.add('uploading');
    document.getElementById('upload-text').textContent = '파싱 중...';
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('rules_kie', 'false');
    
    try {
        const response = await fetch('/parse', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('파싱 실패');
        }
        
        const result = await response.json();
        currentResult = result;
        
        displayResults(result);
        showAlert('파싱 완료!', 'success');
        
    } catch (error) {
        showAlert('오류 발생: ' + error.message, 'error');
    } finally {
        uploadZone.classList.remove('uploading');
        document.getElementById('upload-text').textContent = '클릭하거나 파일을 드래그하세요';
    }
}

// 결과 표시
function displayResults(result) {
    const formStructure = result.form_structure || {};
    
    // 통계 업데이트
    document.getElementById('stat-title').textContent = formStructure.title || 'N/A';
    document.getElementById('stat-sections').textContent = (formStructure.sections || []).length;
    
    const formElements = formStructure.form_elements || {};
    const totalElements = 
        (formElements.text_inputs || []).length +
        (formElements.checkboxes || []).length +
        (formElements.buttons || []).length +
        (formElements.file_uploads || []).length;
    
    document.getElementById('stat-elements').textContent = totalElements;
    document.getElementById('stat-tables').textContent = (formStructure.tables || []).length;
    
    // 프롬프트 업데이트
    updatePromptDisplay(result);
}

// 프롬프트 표시 업데이트
function updatePromptDisplay(result) {
    const promptText = generatePrompt(result, currentTemplate);
    document.getElementById('prompt-text').textContent = promptText;
}

// 템플릿별 프롬프트 생성
function generatePrompt(result, template) {
    const hybridPrompt = result.hybrid_prompt || '';
    
    switch(template) {
        case 'claude':
            return `# Claude용 문서 작성 어시스턴트

당신은 전문 문서 작성 어시스턴트입니다. 아래 양식 구조를 분석하고, 사용자가 요청하는 내용으로 단계별 작성 가이드를 제공하세요.

${hybridPrompt}`;

        case 'gpt':
            return `# GPT Document Assistant

You are a professional document writing assistant. Analyze the form structure below and provide step-by-step guidance.

${hybridPrompt}`;

        case 'gemini':
            return `# Gemini 문서 작성 도우미

문서 작성 어시스턴트로서 아래 양식을 분석하고 단계별 가이드를 제공하세요.

${hybridPrompt}`;

        default:
            return hybridPrompt;
    }
}

// 복사 버튼
document.getElementById('copy-btn').addEventListener('click', async () => {
    const promptText = document.getElementById('prompt-text').textContent;
    
    try {
        await navigator.clipboard.writeText(promptText);
        
        const btn = document.getElementById('copy-btn');
        const originalText = btn.textContent;
        btn.textContent = '✓ 복사됨!';
        btn.classList.add('copied');
        
        setTimeout(() => {
            btn.textContent = originalText;
            btn.classList.remove('copied');
        }, 2000);
        
    } catch (error) {
        showAlert('복사 실패: ' + error.message, 'error');
    }
});

// 알림 표시
function showAlert(message, type) {
    const existingAlert = document.querySelector('.alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    
    document.querySelector('.container').insertBefore(alert, document.querySelector('.main-content'));
    
    setTimeout(() => alert.remove(), 5000);
}

// JSON 프롬프트 토글 버튼 핸들러
document.getElementById('toggle-json').addEventListener('click', function() {
    const jsonOutput = document.getElementById('json-output');
    const isVisible = jsonOutput.style.display !== 'none';
    
    jsonOutput.style.display = isVisible ? 'none' : 'block';
    this.textContent = isVisible ? '📊 JSON 보기' : '📄 텍스트 보기';
    
    if (!isVisible && currentResult) {
        document.getElementById('json-text').textContent = JSON.stringify(currentResult.json_prompt, null, 2);
    }
});

// JSON 복사 버튼
document.getElementById('copy-json-btn').addEventListener('click', async () => {
    const jsonText = document.getElementById('json-text').textContent;
    
    try {
        await navigator.clipboard.writeText(jsonText);
        
        const btn = document.getElementById('copy-json-btn');
        const originalText = btn.textContent;
        btn.textContent = '✓ 복사됨!';
        btn.classList.add('copied');
        
        setTimeout(() => {
            btn.textContent = originalText;
            btn.classList.remove('copied');
        }, 2000);
        
    } catch (error) {
        showAlert('복사 실패: ' + error.message, 'error');
    }
});