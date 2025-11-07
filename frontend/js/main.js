document.addEventListener('DOMContentLoaded', () => {
    const appContent = document.getElementById('app-content');

    // --- Simple Hash Router ---
    async function router() {
        const hash = window.location.hash || '#home';
        appContent.innerHTML = '<div class="loader"></div>';

        try {
            if (hash.startsWith('#candidate?')) {
                const urlParams = new URLSearchParams(hash.split('?')[1]);
                const candidateId = urlParams.get('id');
                if (candidateId) {
                    await initCandidateDetailPage(candidateId);
                } else {
                    appContent.innerHTML = '<div class="container mt-4"><p class="text-danger">No candidate ID provided.</p></div>';
                }
            } else if (hash === '#dashboard') {
                appContent.innerHTML = await loadPage('dashboard.html');
                await initDashboard();
            } else if (hash === '#upload') {
                appContent.innerHTML = await loadPage('upload.html');
                initUploadPage();
            } else if (hash === '#candidates') {
                appContent.innerHTML = await loadPage('candidates.html');
                await initCandidatesPage(); // Make sure this is called
            } else {
                appContent.innerHTML = `
                    <div class="container mt-4">
                        <h1>Welcome to Resume Hub</h1>
                        <p class="lead">The premier platform for automated resume analysis.</p>
                        <hr style="background-color: var(--accent-color);">
                        <p>Navigate using the sidebar to upload resumes or view candidate data.</p>
                        <a class="btn-custom" href="#upload" role="button">Get Started</a>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading page:', error);
            appContent.innerHTML = '<div class="container mt-4"><p class="text-danger">Error loading page. Please try again.</p></div>';
        }
    }

    async function loadPage(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to fetch page: ${response.statusText}`);
        }
        return await response.text();
    }

    window.addEventListener('hashchange', router);
    router(); // Initial call

    // --- Dashboard Page Logic ---
    async function initDashboard() {
        try {
            const response = await fetch('/api/analytics');
            if (!response.ok) throw new Error('Failed to fetch analytics');
            const analyticsData = await response.json();

            renderSkillsChart(analyticsData.skill_distribution);
            renderExperienceChart(analyticsData.experience_distribution);

        } catch (error) {
            console.error('Error initializing dashboard:', error);
        }
    }

    function renderSkillsChart(skillData) {
        const ctx = document.getElementById('skills-chart');
        if (!ctx) return;
        new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: Object.keys(skillData),
                datasets: [{
                    label: 'Skill Distribution',
                    data: Object.values(skillData),
                    backgroundColor: 'rgba(212, 175, 55, 0.6)',
                    borderColor: 'rgba(212, 175, 55, 1)',
                    borderWidth: 1
                }]
            },
            options: { 
                scales: { y: { beginAtZero: true } },
                plugins: {
                    legend: {
                        labels: { color: '#e0e0e0' }
                    }
                }
            }
        });
    }

    function renderExperienceChart(experienceData) {
        const ctx = document.getElementById('experience-chart');
        if (!ctx) return;
        new Chart(ctx.getContext('2d'), {
            type: 'pie',
            data: {
                labels: Object.keys(experienceData),
                datasets: [{
                    label: 'Experience Distribution',
                    data: Object.values(experienceData),
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.6)',
                        'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 206, 86, 0.6)',
                        'rgba(75, 192, 192, 0.6)',
                        'rgba(153, 102, 255, 0.6)',
                        'rgba(255, 159, 64, 0.6)'
                    ],
                    borderColor: [
                        'rgba(255, 99, 132, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)',
                        'rgba(255, 159, 64, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                plugins: {
                    legend: {
                        labels: { color: '#e0e0e0' }
                    }
                }
            }
        });
    }

    // --- Candidate Detail Page Logic ---
    async function initCandidateDetailPage(candidateId) {
    try {
        const pageHtml = await loadPage('candidate-detail.html');
        appContent.innerHTML = pageHtml;
        
        const response = await fetch(`/api/candidate/${candidateId}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch candidate data: ${response.statusText}`);
        }
        const candidateData = await response.json();

        const templateSource = document.getElementById('candidate-detail-template').innerHTML;
        const template = Handlebars.compile(templateSource);
        const renderedHtml = template(candidateData);
        
        const container = document.getElementById('candidate-detail-container');
        if (container) {
            container.innerHTML = renderedHtml;
        }

        // Automatically load the resume
        loadResumeForCandidate(candidateId);
        
    } catch (error) {
        console.error('Error initializing candidate detail page:', error);
        appContent.innerHTML = '<div class="container mt-4"><p class="text-danger">Error loading candidate details.</p></div>';
    }
}

async function loadResumeForCandidate(candidateId) {
    const container = document.getElementById('resume-viewer-container');
    if (!container) return;
    
    container.innerHTML = '<div class="loader"></div>';
    
    try {
        const response = await fetch(`/api/resume/${candidateId}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                container.innerHTML = '<p class="text-warning">Resume file not found. This might be an older candidate uploaded before file storage was enabled.</p>';
            } else {
                container.innerHTML = '<p class="text-danger">Error loading resume file.</p>';
            }
            return;
        }
        
        const contentType = response.headers.get('content-type');
        console.log('Resume content-type:', contentType); // Debug log
        
        const blob = await response.blob();
        console.log('Blob type:', blob.type); // Debug log
        
        // Check if it's a PDF
        if (contentType && contentType.includes('pdf')) {
            console.log('Rendering as PDF');
            const arrayBuffer = await blob.arrayBuffer();
            const typedarray = new Uint8Array(arrayBuffer);
            
            pdfjsLib.getDocument(typedarray).promise.then(pdf => {
                container.innerHTML = '';
                const promises = [];
                
                for (let i = 1; i <= pdf.numPages; i++) {
                    promises.push(
                        pdf.getPage(i).then(page => {
                            const canvas = document.createElement('canvas');
                            const context = canvas.getContext('2d');
                            const viewport = page.getViewport({ scale: 1.2 });
                            canvas.height = viewport.height;
                            canvas.width = viewport.width;
                            canvas.style.display = 'block';
                            canvas.style.marginBottom = '10px';
                            container.appendChild(canvas);
                            return page.render({ canvasContext: context, viewport: viewport }).promise;
                        })
                    );
                }
                
                return Promise.all(promises);
            }).catch(err => {
                console.error('Error rendering PDF:', err);
                container.innerHTML = '<p class="text-danger">Error rendering PDF file.</p>';
            });
            
        // Check if it's a DOCX
        } else if (contentType && (contentType.includes('wordprocessingml') || contentType.includes('officedocument'))) {
            console.log('Rendering as DOCX');
            const arrayBuffer = await blob.arrayBuffer();
            
            mammoth.convertToHtml({ arrayBuffer: arrayBuffer })
                .then(result => {
                    container.innerHTML = `<div style="background: white; padding: 20px; color: black;">${result.value}</div>`;
                    
                    // Log any warnings
                    if (result.messages && result.messages.length > 0) {
                        console.log('Mammoth conversion messages:', result.messages);
                    }
                })
                .catch(err => {
                    console.error('Error rendering DOCX:', err);
                    container.innerHTML = '<p class="text-danger">Error rendering DOCX file.</p>';
                });
                
        } else {
            console.error('Unsupported content type:', contentType);
            container.innerHTML = `<p class="text-warning">Unsupported file format: ${contentType}</p>`;
        }
        
    } catch (error) {
        console.error('Error loading resume:', error);
        container.innerHTML = '<p class="text-danger">Error loading resume file.</p>';
    }
}


    function renderResume(file) {
        const container = document.getElementById('resume-viewer-container');
        if (!file || !container) {
            if (container) container.innerHTML = '';
            return;
        }

        const reader = new FileReader();
        if (file.type === 'application/pdf') {
            reader.onload = function(e) {
                const typedarray = new Uint8Array(e.target.result);
                pdfjsLib.getDocument(typedarray).promise.then(pdf => {
                    container.innerHTML = '';
                    for (let i = 1; i <= pdf.numPages; i++) {
                        pdf.getPage(i).then(page => {
                            const canvas = document.createElement('canvas');
                            container.appendChild(canvas);
                            const context = canvas.getContext('2d');
                            const viewport = page.getViewport({ scale: 1.5 });
                            canvas.height = viewport.height;
                            canvas.width = viewport.width;
                            page.render({ canvasContext: context, viewport: viewport });
                        });
                    }
                });
            };
            reader.readAsArrayBuffer(file);
        } else if (file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
            reader.onload = function(e) {
                mammoth.convertToHtml({ arrayBuffer: e.target.result })
                    .then(result => {
                        container.innerHTML = result.value;
                    })
                    .catch(err => {
                        console.error('Error rendering DOCX:', err);
                        container.innerHTML = '<p class="text-danger">Error rendering DOCX file.</p>';
                    });
            };
            reader.readAsArrayBuffer(file);
        } else {
            container.innerHTML = '<p class="text-danger">Unsupported file type. Please select a PDF or DOCX file.</p>';
        }
    }

    // --- Upload Page Logic ---
    function initUploadPage() {
        const uploadBtn = document.getElementById('upload-btn');
        const fileInput = document.getElementById('resume-files-input');
        const uploadStatus = document.getElementById('upload-status');

        if (uploadBtn) {
            uploadBtn.addEventListener('click', async () => {
                if (!fileInput) return;
                const files = fileInput.files;
                if (files.length === 0) {
                    if(uploadStatus) uploadStatus.innerHTML = '<p class="text-warning">Please select at least one file.</p>';
                    return;
                }

                const formData = new FormData();
                for (const file of files) {
                    formData.append('files', file);
                }

                if(uploadStatus) uploadStatus.innerHTML = '<div class="loader"></div>';

                try {
                    const response = await fetch('/upload-resumes/', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        const result = await response.json();
                        
                        let message = `<p class="text-success">Successfully processed ${result.processed_files.length} file(s).</p>`;
                        
                        if (result.errors && result.errors.length > 0) {
                            message += '<p class="text-warning">Errors:</p><ul>';
                            result.errors.forEach(err => {
                                message += `<li class="text-warning">${err}</li>`;
                            });
                            message += '</ul>';
                        }
                        
                        if(uploadStatus) uploadStatus.innerHTML = message;
                        
                        if (result.processed_files.length > 0) {
                            setTimeout(() => {
                                window.location.hash = '#candidates';
                            }, 2000);
                        }
                    } else {
                        const error = await response.json();
                        if(uploadStatus) uploadStatus.innerHTML = `<p class="text-danger">Upload failed: ${error.detail || 'Unknown error'}</p>`;
                    }
                } catch (error) {
                    console.error('Error uploading files:', error);
                    if(uploadStatus) uploadStatus.innerHTML = '<p class="text-danger">An unexpected error occurred during upload.</p>';
                }
            });
        }
    }

    // --- Candidates Page Logic ---
    async function initCandidatesPage() {
        console.log('=== initCandidatesPage called ===');
        
        try {
            // Wait for filters to load
            await initFilters();
            
            // Initialize Select2
            if ($.fn.select2) {
                $('#skills-filter').select2({
                    placeholder: 'Select skills',
                    width: '100%'
                });
            }
            
            // Load initial data
            await initCandidatesDataTable();

            // Attach event listeners
            const expFilter = document.getElementById('exp-filter');
            const skillsFilter = document.getElementById('skills-filter');
            const cityFilter = document.getElementById('city-filter');
            const resetBtn = document.getElementById('reset-filters-btn');
            
            if (expFilter) {
                expFilter.addEventListener('change', initCandidatesDataTable);
            }
            if (skillsFilter) {
                skillsFilter.addEventListener('change', initCandidatesDataTable);
            }
            if (cityFilter) {
                cityFilter.addEventListener('change', initCandidatesDataTable);
            }
            
            if (resetBtn) {
                resetBtn.addEventListener('click', () => {
                    if (expFilter) expFilter.value = '';
                    if (cityFilter) cityFilter.value = '';
                    $('#skills-filter').val(null).trigger('change');
                });
            }
        } catch (error) {
            console.error('Error in initCandidatesPage:', error);
        }
    }

    async function initFilters() {
        console.log('=== initFilters called ===');
        try {
            const response = await fetch('/api/filters');
            const filters = await response.json();
            console.log('Filters received:', filters);

            const skillsFilter = document.getElementById('skills-filter');
            if (skillsFilter) {
                skillsFilter.innerHTML = '';
                filters.skills.forEach(skill => {
                    const option = new Option(skill, skill);
                    skillsFilter.add(option);
                });
            }

            const cityFilter = document.getElementById('city-filter');
            if (cityFilter) {
                cityFilter.innerHTML = '<option value="">All</option>';
                filters.cities.forEach(city => {
                    const option = new Option(city, city);
                    cityFilter.add(option);
                });
            }

        } catch (error) {
            console.error('Error initializing filters:', error);
        }
    }

    async function initCandidatesDataTable() {
        console.log('=== initCandidatesDataTable called ===');
        
        const tableBody = document.getElementById('candidates-table-body');
        if (!tableBody) {
            console.error('Table body element not found!');
            return;
        }
        
        // Destroy existing DataTable if it exists
        if ($.fn.DataTable.isDataTable('#candidates-table')) {
            $('#candidates-table').DataTable().destroy();
        }
        
        tableBody.innerHTML = '<tr><td colspan="8" class="text-center"><div class="loader"></div></td></tr>';

        let apiUrl = '/api/candidates/table';
        
        console.log('Fetching candidates from:', apiUrl);

        try {
            const response = await fetch(apiUrl);
            console.log('Response status:', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Received data:', data);
            console.log('Number of candidates:', data.length);
            
            tableBody.innerHTML = '';
            
            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-warning">No candidates found. Please upload some resumes first.</td></tr>';
                return;
            }
            
            data.forEach(candidate => {
                console.log('Processing candidate:', candidate.name);
                const row = `
                    <tr>
                        <td><a href="#candidate?id=${candidate.id}">${candidate.name || 'N/A'}</a></td>
                        <td>${candidate.email || 'N/A'}</td>
                        <td>${candidate.phone || 'N/A'}</td>
                        <td>${candidate.linkedin ? `<a href="${candidate.linkedin}" target="_blank">Profile</a>` : 'N/A'}</td>
                        <td>${candidate.total_exp !== null && candidate.total_exp !== undefined ? candidate.total_exp : 'N/A'}</td>
                        <td>${candidate.city || 'N/A'}</td>
                        <td>${(candidate.skills && candidate.skills.length > 0) ? candidate.skills.join(', ') : 'N/A'}</td>
                        <td>${(candidate.certifications && candidate.certifications.length > 0) ? candidate.certifications.join(', ') : 'N/A'}</td>
                    </tr>
                `;
                tableBody.insertAdjacentHTML('beforeend', row);
            });
            
            console.log('Initializing DataTable...');
            // Initialize DataTable AFTER data is loaded
            $('#candidates-table').DataTable({
                pageLength: 10,
                order: [[0, 'asc']],
                language: {
                    emptyTable: "No candidates found"
                }
            });
            console.log('DataTable initialized successfully');
            
        } catch (error) {
            console.error('Error fetching candidates:', error);
            tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Error loading candidates. Check console for details.</td></tr>';
        }
    }
});