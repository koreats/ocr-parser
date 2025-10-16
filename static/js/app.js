let currentResult = null;

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
        
        console.log('서버 응답:', result); // 디버깅용
        
        displayResults(result);
        showAlert('파싱 완료!', 'success');
        
    } catch (error) {
        console.error('파싱 오류:', error);
        showAlert('오류 발생: ' + error.message, 'error');
    } finally {
        uploadZone.classList.remove('uploading');
        document.getElementById('upload-text').textContent = '클릭하거나 파일을 드래그하세요';
    }
}

// 결과 표시
function displayResults(result) {
    const formStructure = result.form_structure || {};
    
    // 제목 추출 (첫 번째 요소가 제목일 가능성 높음)
    const elements = formStructure.elements || [];
    const firstElement = elements.length > 0 ? elements[0] : null;
    const title = firstElement ? firstElement.label : '문서 제목 없음';
    
    // 섹션 수 계산 (llm_prompt에서 "Section_" 문자열 개수로 추정)
    const llmPrompt = result.llm_prompt || '';
    const sectionMatches = llmPrompt.match(/## Section: Section_\d+/g);
    const sectionCount = sectionMatches ? sectionMatches.length : 0;
    
    // 통계 업데이트
    document.getElementById('stat-title').textContent = title;
    document.getElementById('stat-sections').textContent = sectionCount;
    
    const elementsByType = formStructure.elements_by_type || {};
    const totalElements = formStructure.total_elements || 0;
    
    document.getElementById('stat-elements').textContent = totalElements;
    
    // 표 개수 (ppstructure에서 추출)
    const ppstructure = result.ppstructure || [];
    let tableCount = 0;
    ppstructure.forEach(ps => {
        const tables = ps.tables || [];
        tableCount += tables.length;
    });
    document.getElementById('stat-tables').textContent = tableCount;
    
    // 프롬프트 업데이트
    updatePromptDisplay(result);
}

// 프롬프트 표시 업데이트
function updatePromptDisplay(result) {
    // 핵심 수정: hybrid_prompt → llm_prompt
    const promptText = result.llm_prompt || '';
    
    if (!promptText) {
        console.warn('llm_prompt가 비어있습니다:', result);
        document.getElementById('prompt-text').textContent = 'LLM 프롬프트 생성 실패. 콘솔을 확인하세요.';
        return;
    }
    
    document.getElementById('prompt-text').textContent = promptText;
}

// 복사 버튼
document.getElementById('copy-btn').addEventListener('click', async () => {
    const promptText = document.getElementById('prompt-text').textContent;
    
    if (!promptText || promptText.includes('생성 실패')) {
        showAlert('복사할 프롬프트가 없습니다.', 'error');
        return;
    }
    
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