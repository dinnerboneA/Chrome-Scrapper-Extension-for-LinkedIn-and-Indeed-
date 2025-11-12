document.addEventListener('DOMContentLoaded', () => {
    // --- Selectors ---
    const transferDataButton = document.getElementById('transfer-data-btn');
    const scrapeCurrentPageContainer = document.getElementById('scrape-current-page-container');
    const scrapeCurrentPageButton = document.getElementById('send-website-btn');
    const header = document.getElementById('header');
    const reloadButton = document.getElementById('reload-btn');
    const homeButton = document.getElementById('home-btn');
    const mainView = document.getElementById('initial-view');
    const loadingContent = document.getElementById('loading-content');
    const resultContent = document.getElementById('result-content');
    const urlInput = document.getElementById('url-input');
    const scrapeUrlButton = document.getElementById('scrape-url-btn');

    const reloadIcon = '⟳';
    const searchIconHTML = `<img src="search-icon.png" alt="Search">`;

    // --- Variable to store page status ---
    let currentPageIsFillable = false;

    // --- This listener now reloads data instead of the whole popup ---
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === "scrapingComplete") {
            loadSavedData(); // This re-runs the logic to show the button
        }
    });

    const createCopiableBlock = (parent, contentAsHTML, className = '') => {
        if (!contentAsHTML) return;
        const wrapper = document.createElement('div');
        wrapper.className = 'copiable-line';
        const textEl = document.createElement('div');
        textEl.className = className;
        textEl.innerHTML = contentAsHTML;
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.title = 'Copy to clipboard';
        const copyIconSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
        const checkIconSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        copyBtn.innerHTML = copyIconSVG;
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(textEl.innerText).then(() => {
                copyBtn.innerHTML = checkIconSVG;
                setTimeout(() => { copyBtn.innerHTML = copyIconSVG; }, 1500);
            });
        });
        wrapper.appendChild(textEl);
        wrapper.appendChild(copyBtn);
        parent.appendChild(wrapper);
    };

    const processPage = async (pageHTML, pageUrl) => {
        const apiUrl = 'http://127.0.0.1:8001/api/process-page'; // Using port 8001
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({ html: pageHTML, url: pageUrl }),
        });
        if (!response.ok) { throw new Error(`Server Error: ${response.status}`); }
        return await response.json();
    };

    const handleScrapeCurrentPage = async () => {
        showLoading(false); 
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            const injectionResults = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                function: () => document.documentElement.outerHTML,
            });
            if (chrome.runtime.lastError || !injectionResults || !injectionResults[0]) {
                throw new Error("Could not access page content.");
            }
            const pageHTML = injectionResults[0].result;
            const data = await processPage(pageHTML, tab.url);
            if (data) {
                await chrome.storage.local.set({ profileData: data, lastScrapeMethod: 'currentPage' });
                displayRouter(data, 'currentPage');
            }
        } catch (error) {
            showError(error.message, 'currentPage');
        }
    };
    
    const handleScrapeUrl = () => {
        let url = urlInput.value.trim();
        if (!url || !url.startsWith('http')) {
            showError("Please enter a valid URL.", 'url');
            return;
        }
        if (url.includes('linkedin.com/company/')) {
            const cleanUrl = url.split('?')[0].replace(/\/$/, '');
            if (!cleanUrl.endsWith('/about')) { url = cleanUrl + '/about'; }
        }
        
        showLoading(true); 
        chrome.runtime.sendMessage({ action: "scrapeFromUrl", url: url });
    };

    // --- MODIFIED: handleTransferData ---
    // This now dispatches a custom event to the page
// --- Replace your old handleTransferData with this one ---

    const handleTransferData = () => {
        showLoading(false);
        chrome.storage.local.get(['profileData'], ({ profileData }) => {
            if (!profileData || profileData.error) {
                showError("No scraped data found to transfer.", 'transfer');
                return;
            }

            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (chrome.runtime.lastError) {
                    showError(chrome.runtime.lastError.message, 'transfer');
                    return;
                }
                
                const tabId = tabs[0].id;
                chrome.scripting.executeScript({
                    target: { tabId: tabId },
                    // This is the only code we need to inject.
                    // It just dispatches the event and lets the webpage handle the rest.
                    function: (dataToTransfer) => {
                        try {
                            const event = new CustomEvent('fillFormFromExtension', { detail: dataToTransfer });
                            window.dispatchEvent(event);
                            return { success: true, message: "Data successfully sent to page!" };
                        } catch (e) {
                            return { success: false, message: e.message };
                        }
                    },
                    args: [profileData]
                }, (injectionResults) => {
                    if (chrome.runtime.lastError) {
                        showError(chrome.runtime.lastError.message, 'transfer');
                    } else if (injectionResults && injectionResults[0] && injectionResults[0].result.success) {
                        showSuccess(injectionResults[0].result.message); // Show success animation
                    } else {
                        showError(injectionResults[0]?.result?.message || "Failed to inject script.", 'transfer');
                    }
                });
            });
        });
    };
    // --- End of modification ---

    const displayRouter = (data, source) => {
        // Use the stored variable to check if button should be shown
        if (currentPageIsFillable && data && !data.error) {
            transferDataButton.classList.remove('hidden');
        } else {
            transferDataButton.classList.add('hidden');
        }

        if (!data || data.error) {
            showError(data ? data.error : "Received empty data from server.", source);
            return;
        }
        
        if (data.type === "person") { displayPersonProfile(data); }
        else if (data.type === "job" || data.type === "indeed_job") { displayJobData(data); }
        else if (data.type === "company" || data.type === "indeed_company") { displayCompanyData(data); }
        else { showError(`Unknown data type received: ${data.type || 'N/A'}`, source); }
        
        updateHeaderButton(source);
    };

    const loadSavedData = () => {
        // First, get the page status from session storage
        chrome.storage.session.get(['isPageScrapable', 'isPageFillable'], (sessionData) => {
             currentPageIsFillable = sessionData.isPageFillable || false; // Store status in local variable

             // Now, get the scraped data from local storage
             chrome.storage.local.get(['profileData', 'lastScrapeMethod'], (result) => {
                 if (result.profileData && !result.profileData.error) {
                     displayRouter(result.profileData, result.lastScrapeMethod);
                 } else {
                     showMain(sessionData.isPageScrapable, currentPageIsFillable);
                 }
             });
        });
    };
    
    // --- All display functions are unchanged ---
    const displayPersonProfile = (data) => {
        resultContent.innerHTML = '';
        const headerDiv = document.createElement('div');
        headerDiv.className = 'profile-header';
        if (data.cover_pic_url && data.cover_pic_url !== 'Not available') {
            const coverImg = document.createElement('img');
            coverImg.src = data.cover_pic_url;
            coverImg.className = 'cover-pic';
            headerDiv.appendChild(coverImg);
        }
        if (data.profile_pic_url && data.profile_pic_url !== 'Not available') {
            const profileImg = document.createElement('img');
            profileImg.src = data.profile_pic_url;
            profileImg.className = 'profile-pic';
            headerDiv.appendChild(profileImg);
        }
        resultContent.appendChild(headerDiv);
        createCopiableBlock(resultContent, `<h2>${data.name || 'Name not found'}</h2>`, 'profile-name');
        createCopiableBlock(resultContent, `<p>${data.headline || ''}</p>`, 'profile-headline');
        createCopiableBlock(resultContent, `<p>${data.location || ''}</p>`, 'profile-location');
        resultContent.appendChild(document.createElement('hr'));
        if (data.about && data.about !== 'Not available') {
            resultContent.appendChild(document.createElement('h3')).textContent = 'About';
            createCopiableBlock(resultContent, `<p class="profile-about">${data.about}</p>`);
            resultContent.appendChild(document.createElement('hr'));
        }
        if (Array.isArray(data.experience) && data.experience.length > 0) {
            resultContent.appendChild(document.createElement('h3')).textContent = 'Experience';
            data.experience.forEach(job => {
                const detailsHTML = (job.details && job.details !== 'Not available') ? `<p class="item-details">${job.details}</p>` : '';
                const itemHTML = `<strong>${job.role}</strong><div>${job.company_name} · ${job.job_type}</div><div class="item-dates">${job.date_from} - ${job.date_to}</div><div class="item-location">${job.company_location}</div>${detailsHTML}`;
                createCopiableBlock(resultContent, itemHTML, 'item');
            });
            resultContent.appendChild(document.createElement('hr'));
        }
        if (Array.isArray(data.education) && data.education.length > 0) {
            resultContent.appendChild(document.createElement('h3')).textContent = 'Education';
            data.education.forEach(edu => {
                const detailsHTML = (edu.details && edu.details !== 'Not available') ? `<p class="item-details">${edu.details}</p>` : '';
                const itemHTML = `<strong>${edu.institution_name}</strong><div>${edu.degree}</div><div class="item-dates">${edu.date_from} - ${edu.date_to}</div>${detailsHTML}`;
                createCopiableBlock(resultContent, itemHTML, 'item');
            });
        }


        // --- NEW: Add Skills Section ---
        if (Array.isArray(data.skills) && data.skills.length > 0) {
            resultContent.appendChild(document.createElement('hr'));
            resultContent.appendChild(document.createElement('h3')).textContent = 'Skills';
            const skillsContainer = document.createElement('div');
            skillsContainer.className = 'skills-container';
            data.skills.forEach(skill => {
                const skillEl = document.createElement('span');
                skillEl.className = 'skill-pill';
                skillEl.textContent = skill;
                skillsContainer.appendChild(skillEl);
            });
            resultContent.appendChild(skillsContainer);
        }

        // --- NEW: Add Languages Section ---
        if (Array.isArray(data.languages) && data.languages.length > 0) {
            resultContent.appendChild(document.createElement('hr'));
            resultContent.appendChild(document.createElement('h3')).textContent = 'Languages';
            data.languages.forEach(lang => {
                const itemHTML = `
                    <strong>${lang.language}</strong>
                    <div>${lang.proficiency}</div>
                `;
                const langDiv = document.createElement('div');
                langDiv.className = 'item';
                langDiv.innerHTML = itemHTML;
                resultContent.appendChild(langDiv);
            });
        }
        // --- END OF NEW SECTIONS ---

        showResult();
    };
      
    const displayJobData = (data) => {
        resultContent.innerHTML = '';
        createCopiableBlock(resultContent, `<h2>${data.job_title}</h2>`, 'job-title');
        createCopiableBlock(resultContent, `<p>${data.company_name}</p>`, 'job-company');
        const subHeaderText = [data.location, data.workplace_type, data.date_posted].filter(item => item && item !== 'Not available').join(' · ');
        createCopiableBlock(resultContent, `<div>${subHeaderText}</div>`, 'job-sub-header');
        resultContent.appendChild(document.createElement('hr'));
        const detailsListHTML = `${(data.employment_type && data.employment_type !== 'Not available') ? `<li><strong>Employment Type:</strong> ${data.employment_type}</li>` : ''}${(data.applicants_count && data.applicants_count !== 'Not available') ? `<li><strong>Applicants:</strong> ${data.applicants_count}</li>` : ''}`;
        if (detailsListHTML.trim() !== '') {
            createCopiableBlock(resultContent, `<ul class="job-details-list">${detailsListHTML}</ul>`);
        }
        if (data.job_description && data.job_description !== 'Not available') {
            resultContent.appendChild(document.createElement('h3')).textContent = 'Job Description';
            createCopiableBlock(resultContent, `<p class="job-description">${data.job_description}</p>`);
        }
        showResult();
    };
      
    const displayCompanyData = (data) => {
        resultContent.innerHTML = '';
        const headerDiv = document.createElement('div');
        headerDiv.className = 'profile-header';
        if (data.cover_pic_url && data.cover_pic_url !== 'Not available') {
            const coverImg = document.createElement('img');
            coverImg.src = data.cover_pic_url;
            coverImg.className = 'cover-pic';
            headerDiv.appendChild(coverImg);
        }
        if (data.logo_url && data.logo_url !== 'Not available') {
            const logoImg = document.createElement('img');
            logoImg.src = data.logo_url;
            logoImg.className = 'profile-pic';
            headerDiv.appendChild(logoImg);
        }
        resultContent.appendChild(headerDiv);
        createCopiableBlock(resultContent, `<h2>${data.company_name}</h2>`, 'profile-name');
        createCopiableBlock(resultContent, `<p>${data.tagline}</p>`, 'profile-headline');
        createCopiableBlock(resultContent, `<p>${data.industry}</p>`, 'profile-industry');
        createCopiableBlock(resultContent, `<p>${data.follower_count}</p>`, 'follower-count');
        resultContent.appendChild(document.createElement('hr'));
        if (data.about && data.about !== 'Not available') {
            resultContent.appendChild(document.createElement('h3')).textContent = 'About';
            createCopiableBlock(resultContent, `<p class="profile-about">${data.about}</p>`);
            resultContent.appendChild(document.createElement('hr'));
        }
        resultContent.appendChild(document.createElement('h3')).textContent = 'Company Details';
        const detailsListHTML = `${(data.website && data.website !== 'Not available') ? `<li><strong>Website:</strong> <a href="${data.website}" target="_blank">${data.website}</a></li>` : ''}${(data.company_size && data.company_size !== 'Not available') ? `<li><strong>Company Size:</strong> ${data.company_size}</li>` : ''}${(data.headquarters && data.headquarters !== 'Not available') ? `<li><strong>Headquarters:</strong> ${data.headquarters}</li>` : ''}${(data.founded && data.founded !== 'Not available') ? `<li><strong>Founded:</strong> ${data.founded}</li>` : ''}${(data.specialties && data.specialties !== 'Not available') ? `<li><strong>Specialties:</strong> ${data.specialties}</li>` : ''}`;
        createCopiableBlock(resultContent, `<ul class="company-details-list">${detailsListHTML}</ul>`);
        showResult();
    };

    const updateHeaderButton = (source) => {
        if (source === 'url') {
            reloadButton.innerHTML = searchIconHTML;
            reloadButton.title = 'Scrape another URL';
            reloadButton.classList.remove('reload-icon');
            reloadButton.onclick = handleGoHome;
        } else {
            reloadButton.innerHTML = reloadIcon;
            reloadButton.title = 'Reload Data';
            reloadButton.classList.add('reload-icon');
            reloadButton.onclick = handleScrapeCurrentPage;
        }
    };

    const showLoading = (isBackground = false) => {
        mainView.classList.add('hidden');
        header.classList.add('hidden');
        resultContent.innerHTML = '';
        resultContent.classList.add('hidden');
        loadingContent.classList.remove('hidden');
        if (isBackground) {
            loadingContent.innerHTML = `<div class="loader-spinner"></div><p id="loading-message">Scraping in background...</p>`;
        } else {
            loadingContent.innerHTML = `<div class="loader-spinner"></div>`;
        }
    };

    const showResult = () => { 
        mainView.classList.add('hidden'); 
        loadingContent.classList.add('hidden'); 
        resultContent.classList.remove('hidden'); 
        header.classList.remove('hidden'); // Show the header
    };
    
    const showMain = (isScrapable, isFillable) => {
        loadingContent.classList.add('hidden');
        resultContent.innerHTML = '';
        resultContent.classList.add('hidden');
        header.classList.add('hidden'); // Hide the header
        mainView.classList.remove('hidden');

        if (isScrapable) {
            scrapeCurrentPageContainer.classList.remove('hidden');
        } else {
            scrapeCurrentPageContainer.classList.add('hidden');
        }
        transferDataButton.classList.add('hidden');
    };

    const showError = (message, source) => {
        // Don't hide the transfer button if we're just showing an error message
        if (!currentPageIsFillable) { 
            transferDataButton.classList.add('hidden'); 
        }
        showResult();
        resultContent.innerHTML = `<div class="error-message"><p><strong>Error:</strong> ${message}</p></div>`;
        updateHeaderButton(source);
    };

    // --- NEW: Success Animation Function ---
    const showSuccess = (message) => {
        // 1. Show the loading overlay
        showLoading(false);
        // 2. Populate it with the success animation HTML
        loadingContent.innerHTML = `
            <div class="success-animation">
                <svg class="checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                    <circle class="checkmark__circle" cx="26" cy="26" r="25" fill="none"/>
                    <path class="checkmark__check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
                </svg>
                <p id="loading-message" style="animation: none;">${message}</p>
            </div>
        `;
        // 3. Set a timer to go back to the results
        setTimeout(() => {
            loadSavedData(); // This will re-run displayRouter and show the results again
        }, 2000); // Wait 2 seconds
    };
    // --- END NEW FUNCTION ---

    const handleGoHome = () => {
        transferDataButton.classList.add('hidden'); 
        chrome.storage.local.clear(() => {
            chrome.storage.session.get(['isPageScrapable', 'isPageFillable'], (sessionData) => {
                currentPageIsFillable = sessionData.isPageFillable || false; 
                showMain(sessionData.isPageScrapable, currentPageIsFillable);
            });
        });
    };

    // --- Event Listeners (unchanged) ---
    transferDataButton.addEventListener('click', handleTransferData);
    scrapeCurrentPageButton.addEventListener('click', handleScrapeCurrentPage);
    scrapeUrlButton.addEventListener('click', handleScrapeUrl);
    homeButton.addEventListener('click', handleGoHome);

    loadSavedData(); // Initial load when popup opens
});