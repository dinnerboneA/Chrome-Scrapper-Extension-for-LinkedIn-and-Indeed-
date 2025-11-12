// A list of URL patterns that will activate the extension.
const enabledUrlPatterns = [
  "linkedin.com/in/",
  "linkedin.com/jobs/view/",
  "linkedin.com/company/",
  ["indeed.", "/cmp/"],
  ["indeed.", "/viewjob"]
];

// A list of URL patterns on your site that can be filled
// --- THIS IS THE CLEANED-UP LIST ---
const fillableUrlPatterns = [
  "localhost:8000/setup",                   // Candidate setup page
  "localhost:8000/admin/jobs/setup",      // <-- Your NEW multi-step job page
  "localhost:8000/admin/company/setup",


  // These are the abandoned single-page routes.
  // You can delete them if you want.
  "localhost:8000/admin/jobs/create-single-page",
  "localhost:8000/candidate/create-single-page"
];
// --- END OF FIX ---

function updateExtensionState(tabId, url) {
  if (!url || !url.startsWith("http")) {
    chrome.storage.session.set({ isPageScrapable: false, isPageFillable: false });
    return;
  }
  
  const isEnabled = enabledUrlPatterns.some(pattern => {
    if (Array.isArray(pattern)) return pattern.every(part => url.includes(part));
    return url.includes(pattern);
  });
  
  const isFillable = fillableUrlPatterns.some(pattern => url.includes(pattern));

  console.log("Checking URL:", url);
  console.log("Is Page Scrapable?", isEnabled);
  console.log("Is Page Fillable?", isFillable);

  chrome.storage.session.set({ 
    isPageScrapable: isEnabled,
    isPageFillable: isFillable
  });

  const iconPath = isEnabled ? "icon-active.png" : "icon-default.png";
  const popupPath = "popup.html";
  chrome.action.setIcon({ path: { "48": iconPath }, tabId: tabId });
  chrome.action.setPopup({ tabId: tabId, popup: popupPath });
}

// --- MODIFIED, MORE ROBUST LISTENER ---
// This checks if the tab that finished loading is the one the user is actively looking at.
chrome.webNavigation.onCompleted.addListener((details) => {
  if (details.frameId === 0) {
    chrome.tabs.get(details.tabId, (tab) => {
        // Check if tab exists and has a URL (e.g., not a blank new tab)
        if (tab && tab.url && tab.active) {
            updateExtensionState(details.tabId, details.url);
        }
    });
  }
});

// This listener is crucial for when the user switches tabs.
chrome.tabs.onActivated.addListener((activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, (tab) => {
    if (tab && tab.url) {
      updateExtensionState(tab.id, tab.url);
    } else {
      chrome.storage.session.set({ isPageScrapable: false, isPageFillable: false });
    }
  });
});


// --- ALL THE CODE BELOW IS UNCHANGED ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "scrapeFromUrl") {
    handleScrapeUrlInBackground(message.url);
    return true; 
  }
});

const handleScrapeUrlInBackground = async (url) => {
  let newTab = null;
  try {
    newTab = await chrome.tabs.create({ url: url, active: false });
    await new Promise((resolve, reject) => {
        const listener = (tabId, changeInfo) => {
            if (tabId === newTab.id && changeInfo.status === 'complete') {
                chrome.tabs.onUpdated.removeListener(listener);
                resolve();
            }
        };
        chrome.tabs.onUpdated.addListener(listener);
        setTimeout(() => {
            chrome.tabs.onUpdated.removeListener(listener);
            reject(new Error("Page took too long to load in the background."));
        }, 30000); 
    });
    await new Promise(resolve => setTimeout(resolve, 3000));
    const injectionResults = await chrome.scripting.executeScript({
        target: { tabId: newTab.id },
        function: () => document.documentElement.outerHTML,
    });
    if (chrome.runtime.lastError || !injectionResults || !injectionResults[0]) {
        throw new Error("Could not access content of the provided URL.");
    }
    const pageHTML = injectionResults[0].result;
    const apiUrl = 'http://127.0.0.1:8001/api/process-page'; // Using port 8001
    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html: pageHTML, url: url }),
    });
    if (!response.ok) { throw new Error(`Server Error: ${response.status}`); }
    const data = await response.json();
    await chrome.storage.local.set({ profileData: data, lastScrapeMethod: 'url' });
  } catch (error) {
    await chrome.storage.local.set({ 
        profileData: { error: error.message },
        lastScrapeMethod: 'url'
    });
  } finally {
    if (newTab && newTab.id) {
        await chrome.tabs.remove(newTab.id);
    }
    chrome.runtime.sendMessage({ action: "scrapingComplete" });
  }
};