// A list of URL patterns that will activate the extension.
const enabledUrlPatterns = [
  "linkedin.com/in/",          
  "linkedin.com/jobs/view/",   
  "linkedin.com/company/",     
  ["indeed.", "/cmp/"],        
  ["indeed.", "/viewjob"]      
];

// This is the main function that controls the extension's state.
function updateExtensionState(tabId, url) {
  // Ignore internal Chrome pages.
  if (!url || url.startsWith("chrome://")) {
    return;
  }

  // Check if the current URL matches any of our enabled patterns.
  const isEnabled = enabledUrlPatterns.some(pattern => {
    // If the pattern is an array, all parts must be in the URL.
    if (Array.isArray(pattern)) {
      return pattern.every(part => url.includes(part));
    }
    // Otherwise, just check for the single string.
    return url.includes(pattern);
  });
  
  // Choose the correct icon and decide if the popup should be enabled.
  const iconPath = isEnabled ? "icon-active.png" : "icon-default.png";
  const popupPath = isEnabled ? "popup.html" : ""; // An empty string disables the popup.

  // 1. Set the icon image.
  chrome.action.setIcon({
    path: { "48": iconPath },
    tabId: tabId
  });

  // 2. Enable or disable the popup.
  chrome.action.setPopup({
    tabId: tabId,
    popup: popupPath
  });
}

// Single listener for when a tab is updated (e.g., a page finishes loading).
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    updateExtensionState(tabId, tab.url);
  }
});

// Single listener for when the user switches to a different tab.
chrome.tabs.onActivated.addListener((activeInfo) => {
  // Clear any saved profile data from the previous tab.
  chrome.storage.local.clear();
  
  // Update the extension's state for the newly activated tab.
  chrome.tabs.get(activeInfo.tabId, (tab) => {
    if (tab && tab.url) {
      updateExtensionState(tab.id, tab.url);
    }
  });
});

// Set the initial state for the active tab when the extension first starts.
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs[0] && tabs[0].url) {
    updateExtensionState(tabs[0].id, tabs[0].url);
  }
});