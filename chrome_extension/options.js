document.addEventListener('DOMContentLoaded', function() {
  const serverUrlInput = document.getElementById('serverUrl');
  const saveButton = document.getElementById('saveButton');
  const testButton = document.getElementById('testButton');
  const statusElem = document.getElementById('status');
  
  // 加载保存的服务器地址
  chrome.storage.sync.get(['serverUrl'], function(result) {
    serverUrlInput.value = result.serverUrl || 'http://localhost:5000';
  });
  
  // 保存设置
  saveButton.addEventListener('click', function() {
    let serverUrl = serverUrlInput.value.trim();
    
    // 验证URL格式
    if (!serverUrl.startsWith('http://') && !serverUrl.startsWith('https://')) {
      showStatus('错误：URL必须以http://或https://开头', 'error');
      return;
    }
    
    // 移除URL末尾的斜杠
    if (serverUrl.endsWith('/')) {
      serverUrl = serverUrl.slice(0, -1);
    }
    
    // 保存设置
    chrome.storage.sync.set({serverUrl: serverUrl}, function() {
      showStatus('设置已保存！', 'success');
    });
  });
  
  // 测试服务器连接
  testButton.addEventListener('click', function() {
    let serverUrl = serverUrlInput.value.trim();
    
    // 验证URL格式
    if (!serverUrl.startsWith('http://') && !serverUrl.startsWith('https://')) {
      showStatus('错误：URL必须以http://或https://开头', 'error');
      return;
    }
    
    // 移除URL末尾的斜杠
    if (serverUrl.endsWith('/')) {
      serverUrl = serverUrl.slice(0, -1);
    }
    
    // 测试连接
    showStatus('正在测试连接...', '');
    
    fetch(`${serverUrl}/ping`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('服务器返回错误: ' + response.status);
      }
      return response.json();
    })
    .then(data => {
      showStatus('连接成功！服务器响应正常。', 'success');
    })
    .catch(error => {
      showStatus('连接失败: ' + error.message, 'error');
    });
  });
  
  // 显示状态消息
  function showStatus(message, type) {
    statusElem.textContent = message;
    statusElem.style.display = 'block';
    
    // 清除所有类
    statusElem.classList.remove('success', 'error');
    
    // 添加类型
    if (type) {
      statusElem.classList.add(type);
    }
  }
});