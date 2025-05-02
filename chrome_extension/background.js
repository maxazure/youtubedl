// 扩展安装或更新时设置默认值
chrome.runtime.onInstalled.addListener(function() {
  chrome.storage.sync.get(['serverUrl'], function(result) {
    if (!result.serverUrl) {
      chrome.storage.sync.set({serverUrl: 'http://192.168.31.205:8871/api'});
    }
  });
});