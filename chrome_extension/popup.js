document.addEventListener('DOMContentLoaded', function() {
  const currentUrlElem = document.getElementById('currentUrl');
  const sendButton = document.getElementById('sendButton');
  const statusElem = document.getElementById('status');
  const errorElem = document.getElementById('error');
  const optionsButton = document.getElementById('optionsButton');
  
  // 获取当前标签页的URL
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    let currentTab = tabs[0];
    let url = currentTab.url;
    
    // 检查是否为YouTube视频URL
    if (url.includes('youtube.com/watch')) {
      currentUrlElem.textContent = url;
      sendButton.disabled = false;
    } else {
      currentUrlElem.textContent = '当前页面不是YouTube视频页面';
      sendButton.disabled = true;
      errorElem.textContent = '请在YouTube视频页面使用此扩展';
    }
  });
  
  // 发送URL到服务器
  sendButton.addEventListener('click', function() {
    statusElem.textContent = '';
    errorElem.textContent = '';
    
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      let url = tabs[0].url;
      
      // 获取服务器地址
      chrome.storage.sync.get(['serverUrl'], function(result) {
        let serverUrl = result.serverUrl || 'http://192.168.31.205:8871/api';
        
        // 发送请求，使用youtube_url参数
        fetch(`${serverUrl}/tasks/add`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            youtube_url: url
          }),
        })
        .then(response => {
          if (!response.ok) {
            throw new Error('服务器返回错误: ' + response.status);
          }
          return response.json();
        })
        .then(data => {
          statusElem.textContent = '成功添加到下载队列！';
        })
        .catch(error => {
          errorElem.textContent = '错误: ' + error.message;
        });
      });
    });
  });
  
  // 打开设置页面
  optionsButton.addEventListener('click', function() {
    chrome.runtime.openOptionsPage();
  });
});