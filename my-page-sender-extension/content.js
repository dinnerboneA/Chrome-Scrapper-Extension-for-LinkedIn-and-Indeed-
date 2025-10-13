// This script now only acts as a listener for messages from popup.js

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "get_page_data") {
    const pageData = {
      html: document.documentElement.outerHTML
    };
    sendResponse(pageData);
  }
  // Return true to indicate you wish to send a response asynchronously
  return true;
});

requestDataFromServer();