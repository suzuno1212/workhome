// 共通の初期化処理
document.addEventListener('DOMContentLoaded', function () {
    // CAPTCHAの更新処理
    initializeCaptchaRefresh();

    // 相談関連の機能初期化
    initializeConsultation();

    // ログアウト処理の初期化
    initializeLogout();
});

// CAPTCHA更新機能
function initializeCaptchaRefresh() {
    const refreshButtons = document.querySelectorAll('.refresh-captcha');
    refreshButtons.forEach(button => {
        button.addEventListener('click', async function (e) {
            e.preventDefault();
            const button = this;
            const captchaContainer = document.querySelector('.captcha');

            button.disabled = true;

            try {
                const response = await fetch('/refresh-captcha', {
                    method: 'GET',
                    headers: {
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    }
                });

                const result = await response.json();

                if (result.status === 'success') {
                    captchaContainer.innerHTML = result.captcha_html;
                    const captchaInput = document.querySelector('input[name="captcha"]');
                    if (captchaInput) {
                        captchaInput.value = '';
                    }
                } else {
                    console.error('CAPTCHA更新エラー:', result.message);
                }
            } catch (error) {
                console.error('CAPTCHA更新エラー:', error);
            } finally {
                button.disabled = false;
            }
        });
    });
}

// 相談機能の初期化
function initializeConsultation() {
    const consultationHistory = document.getElementById('consultationHistory');
    if (consultationHistory) {
        consultationHistory.scrollTop = consultationHistory.scrollHeight;
    }

    const consultationForm = document.getElementById('consultationForm');
    if (consultationForm) {
        consultationForm.addEventListener('submit', handleConsultationSubmit);
    }

    const consultationImages = document.getElementById('consultationImages');
    if (consultationImages) {
        consultationImages.addEventListener('change', handleImagePreview);
    }
}

// 相談フォーム送信処理
async function handleConsultationSubmit(e) {
    e.preventDefault();
    const submitButton = document.getElementById('submitButton');
    submitButton.disabled = true;

    try {
        const formData = new FormData(this);
        const response = await fetch('/member/consultation/submit', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (result.status === 'success') {
            const modal = bootstrap.Modal.getInstance(document.getElementById('newConsultationModal'));
            modal.hide();
            this.reset();
            document.getElementById('imagePreview').innerHTML = '';
            location.reload();
        } else {
            alert(result.message || '相談の送信に失敗しました');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('エラーが発生しました');
    } finally {
        submitButton.disabled = false;
    }
}

// 画像プレビュー処理
function handleImagePreview(e) {
    const preview = document.getElementById('imagePreview');
    preview.innerHTML = '';

    [...e.target.files].forEach(file => {
        if (!file.type.startsWith('image/')) {
            alert('画像ファイルのみアップロード可能です');
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'img-thumbnail';
            img.style.maxWidth = '100px';
            preview.appendChild(img);
        }
        reader.readAsDataURL(file);
    });
}

// 画像拡大表示
function showImageModal(src) {
    const modalImage = document.getElementById('modalImage');
    modalImage.src = src;
    new bootstrap.Modal(document.getElementById('imageModal')).show();
}

// ログアウト処理の初期化
function initializeLogout() {
    const logoutButton = document.querySelector('#confirmLogout');
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }
}

// ログアウト処理
async function handleLogout() {
    try {
        const response = await fetch('/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            // ログアウト成功時にホームページにリダイレクト
            window.location.href = '/';
        } else {
            throw new Error('Logout failed');
        }
    } catch (error) {
        console.error('Logout error:', error);
        alert('ログアウトに失敗しました');
    }
}