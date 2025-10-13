document.addEventListener('DOMContentLoaded', () => {
  const sendButton = document.getElementById('send-website-btn');
  const reloadButton = document.getElementById('reload-btn');
  const mainContent = document.getElementById('main-content');
  const loadingContent = document.getElementById('loading-content');
  const resultContent = document.getElementById('result-content');

  // --- HELPER FUNCTION FOR CREATING COPIABLE BLOCKS ---
  const createCopiableBlock = (parent, contentAsHTML, className = '') => {
    if (!contentAsHTML) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'copiable-line';

    const textEl = document.createElement('div');
    textEl.className = className;
    textEl.innerHTML = contentAsHTML; // Use innerHTML to render bold/other tags
    
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.title = 'Copy to clipboard';
    const copyIconSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
    const checkIconSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    copyBtn.innerHTML = copyIconSVG;
    
    copyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        // Copy the plain text version of the rendered HTML
        navigator.clipboard.writeText(textEl.innerText).then(() => {
            copyBtn.innerHTML = checkIconSVG;
            setTimeout(() => {
                copyBtn.innerHTML = copyIconSVG;
            }, 1500);
        });
    });

    wrapper.appendChild(textEl);
    wrapper.appendChild(copyBtn);
    parent.appendChild(wrapper);
  };
  
  // --- CORE LOGIC & ROUTER ---
  const fetchAndDisplayData = async () => {
    showLoading();
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const injectionResults = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        function: () => document.documentElement.outerHTML,
      });

      if (chrome.runtime.lastError || !injectionResults || !injectionResults[0]) {
        throw new Error("Could not access page content. This page may be protected by Chrome.");
      }
      
      const pageHTML = injectionResults[0].result;
      const pageUrl = tab.url;

      const apiUrl = 'http://127.0.0.1:8000/api/process-page';
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ html: pageHTML, url: pageUrl }),
      });

      if (!response.ok) { throw new Error(`Server Error: ${response.status}`); }
      
      const serverData = await response.json();
      
      chrome.storage.local.set({ profileData: serverData });
      displayRouter(serverData);

    } catch (error) {
      showError(error.message);
    }
  };

  const displayRouter = (data) => {
    if (!data || data.error) {
      showError(data ? data.error : "Received empty data from server.");
      return;
    }
    if (data.type === "person") { displayPersonProfile(data); }
    else if (data.type === "job") { displayJobData(data); }
    else if (data.type === "company") { displayCompanyData(data); }
    else if (data.type === "indeed_company") {displayCompanyData(data);}
    else if (data.type === "indeed_job") {displayIndeedJobData(data);}          // <-- ADD THIS
    else { showError(`Unknown data type received: ${data.type || 'N/A'}`); }
  };

  const loadSavedData = () => {
    chrome.storage.local.get(['profileData'], (result) => {
      if (result.profileData) {
        displayRouter(result.profileData);
      } else {
        showMain();
      }
    });
  };

  // --- DISPLAY FUNCTIONS ---

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
        const itemHTML = `
            <strong>${job.role}</strong>
            <div>${job.company_name} · ${job.job_type}</div>
            <div class="item-dates">${job.date_from} - ${job.date_to}</div>
            <div class="item-location">${job.company_location}</div>
            ${detailsHTML}
        `;
        createCopiableBlock(resultContent, itemHTML, 'item');
      });
      resultContent.appendChild(document.createElement('hr'));
    }

    if (Array.isArray(data.education) && data.education.length > 0) {
      resultContent.appendChild(document.createElement('h3')).textContent = 'Education';
      data.education.forEach(edu => {
        const detailsHTML = (edu.details && edu.details !== 'Not available') ? `<p class="item-details">${edu.details}</p>` : '';
        const itemHTML = `
            <strong>${edu.institution_name}</strong>
            <div>${edu.degree}</div>
            <div class="item-dates">${edu.date_from} - ${edu.date_to}</div>
            ${detailsHTML}
        `;
        createCopiableBlock(resultContent, itemHTML, 'item');
      });
    }
    
    showResult();
  };
  
  const displayJobData = (data) => {
    resultContent.innerHTML = '';

    createCopiableBlock(resultContent, `<h2>${data.job_title}</h2>`, 'job-title');
    createCopiableBlock(resultContent, `<p>${data.company_name}</p>`, 'job-company');
    
    const subHeaderText = [data.location, data.workplace_type, data.date_posted]
        .filter(item => item && item !== 'Not available')
        .join(' · ');
    createCopiableBlock(resultContent, `<div>${subHeaderText}</div>`, 'job-sub-header');
    resultContent.appendChild(document.createElement('hr'));

    const detailsListHTML = `
        ${(data.employment_type && data.employment_type !== 'Not available') ? `<li><strong>Employment Type:</strong> ${data.employment_type}</li>` : ''}
        ${(data.applicants_count && data.applicants_count !== 'Not available') ? `<li><strong>Applicants:</strong> ${data.applicants_count}</li>` : ''}
    `;
    if (detailsListHTML.trim() !== '') {
        createCopiableBlock(resultContent, `<ul class="job-details-list">${detailsListHTML}</ul>`);
    }

    if (data.job_description && data.job_description !== 'Not available') {
      resultContent.appendChild(document.createElement('h3')).textContent = 'Job Description';
      createCopiableBlock(resultContent, `<p>${data.job_description}</p>`, 'job-description');
    }
    showResult();
  };
  
  function displayIndeedJobData(data) {
    displayJobData(data); // Re-use the existing job display function
  }


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
      createCopiableBlock(resultContent, `<p>${data.about}</p>`, 'profile-about');
      resultContent.appendChild(document.createElement('hr'));
    }
    
    resultContent.appendChild(document.createElement('h3')).textContent = 'Company Details';
    const detailsHTML = `
        ${(data.website && data.website !== 'Not available') ? `<li><strong>Website:</strong> <a href="${data.website}" target="_blank">${data.website}</a></li>` : ''}
        ${(data.company_size && data.company_size !== 'Not available') ? `<li><strong>Company Size:</strong> ${data.company_size}</li>` : ''}
        ${(data.headquarters && data.headquarters !== 'Not available') ? `<li><strong>Headquarters:</strong> ${data.headquarters}</li>` : ''}
        ${(data.founded && data.founded !== 'Not available') ? `<li><strong>Founded:</strong> ${data.founded}</li>` : ''}
        ${(data.specialties && data.specialties !== 'Not available') ? `<li><strong>Specialties:</strong> ${data.specialties}</li>` : ''}
    `;
    createCopiableBlock(resultContent, `<ul class="company-details-list">${detailsHTML}</ul>`);

    showResult();
  };

  // --- UI State Changers & Event Listeners ---
  const showLoading = () => { mainContent.classList.add('hidden'); resultContent.classList.add('hidden'); loadingContent.classList.remove('hidden'); };
  const showResult = () => { mainContent.classList.add('hidden'); loadingContent.classList.add('hidden'); resultContent.classList.remove('hidden'); };
  const showMain = () => { loadingContent.classList.add('hidden'); resultContent.classList.add('hidden'); mainContent.classList.remove('hidden'); };
  const showError = (message) => { loadingContent.classList.add('hidden'); mainContent.classList.add('hidden'); resultContent.classList.remove('hidden'); resultContent.innerHTML = `<p><strong>Error:</strong> ${message}</p>`; };

  sendButton.addEventListener('click', fetchAndDisplayData);
  reloadButton.addEventListener('click', fetchAndDisplayData);

  loadSavedData();
});