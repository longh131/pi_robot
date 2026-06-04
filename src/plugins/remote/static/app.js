let isRemote = false;
let isLoggedIn = false;
let currentUser = null;
let accessToken = null;
let heartbeatInterval = null;
let currentSpeed = 50;

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        if (data.motor_speed !== undefined) {
            currentSpeed = data.motor_speed;
            const slider = document.getElementById('speedSlider');
            const valueDisplay = document.getElementById('speedValue');
            if (slider) slider.value = currentSpeed;
            if (valueDisplay) valueDisplay.textContent = currentSpeed + '%';
        }
    } catch (e) {
        console.error('获取配置失败', e);
    }
}

// 页面加载完成后立即获取配置
document.addEventListener('DOMContentLoaded', loadConfig);

async function loadInitialSpeed() {
    try {
        const response = await fetch('/api/command', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + accessToken
            },
            body: JSON.stringify({ command: 'get_status' })
        });
        const data = await response.json();
        if (data.status === 'ok' && data.speed !== undefined) {
            currentSpeed = data.speed;
            document.getElementById('speedSlider').value = currentSpeed;
            document.getElementById('speedValue').textContent = currentSpeed + '%';
        }
    } catch (e) {
        console.error('获取初始速度失败', e);
    }
}

function startVideoFeed() {
    const videoFeed = document.getElementById('videoFeed');
    const videoPlaceholder = document.getElementById('videoPlaceholder');
    
    if (accessToken) {
        videoFeed.src = `/api/video_feed?token=${accessToken}`;
        videoFeed.style.display = 'block';
        videoPlaceholder.style.display = 'none';
    }
}

function stopVideoFeed() {
    const videoFeed = document.getElementById('videoFeed');
    const videoPlaceholder = document.getElementById('videoPlaceholder');
    
    videoFeed.src = '';
    videoFeed.style.display = 'none';
    videoPlaceholder.style.display = 'block';
}

function getAuthHeader() {
    if (!accessToken) return {};
    return { 'Authorization': 'Bearer ' + accessToken };
}

async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (!username || !password) {
        document.getElementById('loginMessage').innerHTML = '<span class="error">❌ 用户名和密码不能为空</span>';
        return;
    }

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            accessToken = data.access_token;
            currentUser = data.username;
            isLoggedIn = true;

            localStorage.setItem('access_token', accessToken);
            localStorage.setItem('username', currentUser);

            document.getElementById('loginMessage').innerHTML = '';
            document.getElementById('loginBox').style.display = 'none';
            document.getElementById('controlPanel').style.display = 'block';
            document.getElementById('userInfo').innerHTML = `当前用户: ${currentUser}`;

            await loadInitialSpeed();
            updateState();
            setInterval(updateState, 1000);
        } else {
            document.getElementById('loginMessage').innerHTML = `<span class="error">❌ ${data.error}</span>`;
            if (response.status === 403) {
                document.getElementById('btnRefresh').style.display = 'block';
            } else {
                document.getElementById('btnRefresh').style.display = 'none';
            }
        }
    } catch (e) {
        console.error('登录失败', e);
        document.getElementById('loginMessage').innerHTML = '<span class="error">❌ 登录失败，请重试</span>';
        document.getElementById('btnRefresh').style.display = 'none';
    }
}

async function checkRobotStatus() {
    try {
        const response = await fetch('/api/state');
        const data = await response.json();

        if (data.state === 'idle') {
            document.getElementById('loginMessage').innerHTML = '<span class="success">✅ 机器人已就绪，可以登录</span>';
            document.getElementById('btnRefresh').style.display = 'none';
        } else if (data.state === 'awake') {
            document.getElementById('loginMessage').innerHTML = '<span class="error">🔴 机器人正在工作中，请稍后再试</span>';
        } else if (data.state === 'remote') {
            document.getElementById('loginMessage').innerHTML = '<span class="error">🔴 机器人已被其他用户远程控制</span>';
        }
    } catch (e) {
        console.error('状态检查失败', e);
    }
}

async function updateState() {
    try {
        const response = await fetch('/api/state');
        const data = await response.json();
        const state = data.state;
        const btnLogout = document.getElementById('btnLogout');
        const mainLayout = document.getElementById('mainLayout');
        const headerStatus = document.getElementById('headerStatus');

        if (state === 'remote') {
            isRemote = true;
            headerStatus.innerHTML = '✅ 远程控制已连接';
            headerStatus.className = 'header-status remote';
            enableButtons(true);
            btnLogout.textContent = '🔌 退出登录';
            btnLogout.onclick = logout;
            btnLogout.className = 'header-btn';
            mainLayout.classList.remove('hidden');
            startVideoFeed();
        } else if (state === 'awake') {
            isRemote = false;
            headerStatus.innerHTML = '🔴 机器人正在工作中';
            headerStatus.className = 'header-status awake';
            enableButtons(false);
            btnLogout.textContent = '🔄 刷新状态';
            btnLogout.onclick = refreshAndReconnect;
            btnLogout.className = 'header-btn refreshing';
            mainLayout.classList.add('hidden');
            stopVideoFeed();
        } else {
            isRemote = false;
            headerStatus.innerHTML = '⚪ 待机中';
            headerStatus.className = 'header-status idle';
            enableButtons(false);
            btnLogout.textContent = '🔌 退出登录';
            btnLogout.onclick = logout;
            btnLogout.className = 'header-btn';
            mainLayout.classList.remove('hidden');
            stopVideoFeed();
            connect();
        }
    } catch (e) {
        console.error('状态获取失败', e);
    }
}

async function refreshAndReconnect() {
    try {
        const response = await fetch('/api/state');
        const data = await response.json();

        if (data.state === 'idle') {
            document.getElementById('message').innerHTML = '<span class="success">✅ 机器人已就绪，正在重新连接...</span>';
            setTimeout(() => {
                document.getElementById('message').innerHTML = '';
            }, 2000);
            connect();
        } else if (data.state === 'awake') {
            document.getElementById('message').innerHTML = '<span class="warning">🔄 机器人仍在工作中，稍后再试</span>';
            setTimeout(() => {
                document.getElementById('message').innerHTML = '';
            }, 2000);
        } else if (data.state === 'remote') {
            document.getElementById('message').innerHTML = '<span class="error">🔴 机器人已被其他用户远程控制</span>';
            setTimeout(() => {
                document.getElementById('message').innerHTML = '';
            }, 2000);
        }
    } catch (e) {
        console.error('状态检查失败', e);
    }
}

async function sendHeartbeat() {
    try {
        await fetch('/api/heartbeat', {
            method: 'POST',
            headers: getAuthHeader()
        });
    } catch (e) {
        console.error('心跳发送失败', e);
    }
}

function enableButtons(enabled) {
    const btns = ['btn_forward', 'btn_stop', 'btn_backward', 'btn_left', 'btn_right'];
    btns.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = !enabled;
    });

    const funcBtns = ['btnRecord', 'btnPhoto', 'btnMusic'];
    funcBtns.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = !enabled;
    });
}

async function connect() {
    if (!isLoggedIn) return;

    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: getAuthHeader()
        });
        const data = await response.json();
        if (response.ok) {
            updateState();
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            heartbeatInterval = setInterval(sendHeartbeat, 3000);
        } else {
            document.getElementById('message').innerHTML = `<span class="error">❌ ${data.error}</span>`;
            setTimeout(() => {
                document.getElementById('message').innerHTML = '';
            }, 3000);
            updateState();
        }
    } catch (e) {
        console.error('连接失败', e);
    }
}

async function logout() {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            headers: getAuthHeader()
        });

        accessToken = null;
        currentUser = null;
        isLoggedIn = false;
        isRemote = false;

        localStorage.removeItem('access_token');
        localStorage.removeItem('username');

        if (heartbeatInterval) {
            clearInterval(heartbeatInterval);
            heartbeatInterval = null;
        }

        stopVideoFeed();

        document.getElementById('controlPanel').style.display = 'none';
        document.getElementById('loginBox').style.display = 'block';
        document.getElementById('username').value = '';
        document.getElementById('password').value = '';
        document.getElementById('loginMessage').innerHTML = '';
    } catch (e) {
        console.error('退出失败', e);
    }
}

async function sendCommand(cmd, params = {}) {
    if (!isRemote) {
        document.getElementById('message').innerHTML = '<span class="error">❌ 非远程控制状态，无法执行命令</span>';
        setTimeout(() => {
            document.getElementById('message').innerHTML = '';
        }, 2000);
        return;
    }

    try {
        const response = await fetch('/api/command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeader()
            },
            body: JSON.stringify({ command: cmd, params: params })
        });
        const data = await response.json();
        if (data.error) {
            document.getElementById('message').innerHTML = `<span class="error">❌ ${data.error}</span>`;
            setTimeout(() => {
                document.getElementById('message').innerHTML = '';
            }, 2000);
        } else if (data.speed !== undefined) {
            currentSpeed = data.speed;
            updateSpeedDisplay();
        }
    } catch (e) {
        console.error('命令发送失败', e);
    }
}

function updateSpeedDisplay() {
    const speedDisplay = document.getElementById('speedValue');
    if (speedDisplay) {
        speedDisplay.textContent = currentSpeed + '%';
    }
    const speedSlider = document.getElementById('speedSlider');
    if (speedSlider) {
        speedSlider.value = currentSpeed;
    }
}

function speedUp() {
    sendCommand('speed_up');
}

function speedDown() {
    sendCommand('speed_down');
}

function setSpeed() {
    const speedSlider = document.getElementById('speedSlider');
    if (speedSlider) {
        sendCommand('set_speed', { speed: parseInt(speedSlider.value) });
    }
}

function checkSavedToken() {
    const savedToken = localStorage.getItem('access_token');
    const savedUser = localStorage.getItem('username');

    if (savedToken && savedUser) {
        accessToken = savedToken;
        currentUser = savedUser;
        isLoggedIn = true;

        document.getElementById('loginBox').style.display = 'none';
        document.getElementById('controlPanel').style.display = 'block';
        document.getElementById('userInfo').innerHTML = `当前用户: ${currentUser}`;

        updateState();
        setInterval(updateState, 1000);
    } else {
        document.getElementById('loginBox').style.display = 'block';
        document.getElementById('controlPanel').style.display = 'none';
    }
}

document.getElementById('speedSlider').addEventListener('input', function(e) {
    const value = e.target.value;
    document.getElementById('speedValue').textContent = value + '%';
});

async function toggleRecording() {
    const btn = document.getElementById('btnRecord');

    if (btn.textContent.includes('开始')) {
        try {
            const response = await fetch('/api/command', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + accessToken
                },
                body: JSON.stringify({ command: 'start_record' })
            });
            const data = await response.json();
            if (data.status === 'ok') {
                btn.textContent = '⏹️ 结束录像';
                btn.classList.add('recording');
                document.getElementById('message').innerHTML = '<span class="warning">📹 录像已开始</span>';
            } else {
                document.getElementById('message').innerHTML = '<span class="error">❌ 录像启动失败</span>';
            }
        } catch (e) {
            console.error('录像启动失败', e);
            document.getElementById('message').innerHTML = '<span class="error">❌ 录像启动失败</span>';
        }
    } else {
        try {
            const response = await fetch('/api/command', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + accessToken
                },
                body: JSON.stringify({ command: 'stop_record' })
            });
            const data = await response.json();
            if (data.status === 'ok') {
                btn.textContent = '⏺️ 开始录像';
                btn.classList.remove('recording');
                document.getElementById('message').innerHTML = `<span class="success">✅ 录像已保存: ${data.filename}</span>`;
                loadMediaList();
            } else {
                document.getElementById('message').innerHTML = `<span class="error">❌ 录像停止失败: ${data.message}</span>`;
            }
        } catch (e) {
            console.error('录像停止失败', e);
            document.getElementById('message').innerHTML = '<span class="error">❌ 录像停止失败</span>';
        }
    }
    setTimeout(() => { document.getElementById('message').innerHTML = ''; }, 3000);
}

async function loadMediaList() {
    try {
        const response = await fetch('/api/media', {
            headers: { 'Authorization': 'Bearer ' + accessToken }
        });
        const data = await response.json();
        if (data.error) {
            console.error('获取媒体列表失败', data.error);
            return;
        }
        
        const mediaList = document.getElementById('mediaList');
        const activeTab = document.querySelector('.media-tab.active');
        const tabType = activeTab.textContent.includes('录像') ? 'videos' : 
                        activeTab.textContent.includes('照片') ? 'photos' : 'music';
        
        const files = data[tabType] || [];
        
        if (files.length === 0) {
            mediaList.innerHTML = '<div class="media-item"><span>暂无文件</span></div>';
            return;
        }
        
        mediaList.innerHTML = files.map((filename, index) => `
            <div class="media-item">
                <span>${filename}</span>
                <button onclick="playMedia('${filename}', ${index})">查看</button>
            </div>
        `).join('');
    } catch (e) {
        console.error('获取媒体列表失败', e);
    }
}

async function takePhoto() {
    try {
        const response = await fetch('/api/command', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + accessToken
            },
            body: JSON.stringify({ command: 'take_photo' })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            document.getElementById('message').innerHTML = `<span class="success">📷 拍照成功: ${data.filename}</span>`;
            loadMediaList();
        } else {
            document.getElementById('message').innerHTML = `<span class="error">❌ 拍照失败: ${data.message}</span>`;
        }
    } catch (e) {
        console.error('拍照失败', e);
        document.getElementById('message').innerHTML = '<span class="error">❌ 拍照失败</span>';
    }
    setTimeout(() => { document.getElementById('message').innerHTML = ''; }, 2000);
}

function playMusic() {
    const playbackControls = document.getElementById('playbackControls');
    playbackControls.classList.add('show');
    document.getElementById('message').innerHTML = '<span class="success">🎵 音乐播放中</span>';
    setTimeout(() => { document.getElementById('message').innerHTML = ''; }, 2000);
}

let currentPlaylist = [];
let currentIndex = 0;
let currentTabType = 'videos';

function playMedia(filename, index) {
    const activeTab = document.querySelector('.media-tab.active');
    currentTabType = activeTab.textContent.includes('录像') ? 'videos' : 
                    activeTab.textContent.includes('照片') ? 'photos' : 'music';
    
    const mediaItems = document.querySelectorAll('.media-item');
    currentPlaylist = [];
    mediaItems.forEach(item => {
        const name = item.querySelector('span').textContent;
        if (name !== '暂无文件') {
            currentPlaylist.push(name);
        }
    });
    currentIndex = index !== undefined ? index : currentPlaylist.indexOf(filename);
    
    openPlayback(filename);
}

function openPlayback(filename) {
    const wrapper = document.getElementById('playbackWrapper');
    const content = document.getElementById('playbackContent');
    const title = document.getElementById('playbackTitle');
    
    title.textContent = filename;
    
    if (currentTabType === 'photos') {
        const imgUrl = `/api/media/file?filename=${encodeURIComponent(filename)}&token=${accessToken}`;
        content.innerHTML = `<img src="${imgUrl}" alt="${filename}" class="playback-image" />`;
        const img = content.querySelector('.playback-image');
        img.onclick = function() {
            window.open(imgUrl, '_blank', 'width=800,height=600,scrollbars=yes,resizable=yes');
        };
    } else if (currentTabType === 'music') {
        const audioUrl = `/api/media/file?filename=${encodeURIComponent(filename)}&token=${accessToken}`;
        content.innerHTML = `<audio src="${audioUrl}" controls class="playback-audio"></audio>`;
        const audio = content.querySelector('audio');
        audio.addEventListener('ended', () => {
            nextMedia();
        });
    } else {
        const videoUrl = `/api/media/file?filename=${encodeURIComponent(filename)}&token=${accessToken}`;
        content.innerHTML = `<video src="${videoUrl}" controls class="playback-video"></video>`;
    }
    
    wrapper.style.display = 'block';
}

function closePlayback() {
    const wrapper = document.getElementById('playbackWrapper');
    const content = document.getElementById('playbackContent');
    
    const audio = content.querySelector('audio');
    if (audio) {
        audio.pause();
    }
    
    const video = content.querySelector('video');
    if (video) {
        video.pause();
    }
    
    wrapper.style.display = 'none';
}

function prevMedia() {
    if (currentPlaylist.length === 0) return;
    currentIndex = (currentIndex - 1 + currentPlaylist.length) % currentPlaylist.length;
    openPlayback(currentPlaylist[currentIndex]);
}

function nextMedia() {
    if (currentPlaylist.length === 0) return;
    currentIndex = (currentIndex + 1) % currentPlaylist.length;
    openPlayback(currentPlaylist[currentIndex]);
}

function switchMediaTab(tab) {
    const tabs = document.querySelectorAll('.media-tab');
    tabs.forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    
    loadMediaList();
}

checkSavedToken();

window.addEventListener('beforeunload', function() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
    }
});