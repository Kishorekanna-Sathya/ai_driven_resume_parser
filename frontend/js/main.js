document.addEventListener('DOMContentLoaded', () => {
    const appContent = document.getElementById('app-content');

    // --- Simple Hash Router ---
    async function router() {
        const hash = window.location.hash || '#home';
        appContent.innerHTML = '<div class="loader"></div>';

        try {
            if (hash.startsWith('#candidate')) {
                const urlParams = new URLSearchParams(hash.split('?')[1]);
                const candidateId = urlParams.get('id');
                if (candidateId) {
                    await initCandidateDetailPage(candidateId);
                } else {
                    appContent.innerHTML = '<div class="container mt-4"><p class="text-danger">No candidate ID provided.</p></div>';
                }
            } else if (hash === '#dashboard') {
                appContent.innerHTML = await loadPage('dashboard.html');
                initDashboard();
            } else if (hash === '#upload') {
                appContent.innerHTML = await loadPage('upload.html');
                initUploadPage();
            } else if (hash === '#candidates') {
                appContent.innerHTML = await loadPage('candidates.html');
                await initCandidatesPage();
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
    // FIX 1: This is the full dashboard logic, replacing the placeholder.
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
                    backgroundColor: 'rgba(75, 192, 192, 0.6)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }]
            },
            options: { scales: { y: { beginAtZero: true } } }
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
            }
        });
    }

    // --- Candidate Detail Page Logic ---
    // FIX 2: Rewritten to use Handlebars to render the template.
    async function initCandidateDetailPage(candidateId) {
        try {
            // 1. Load the HTML file (which contains the template)
            const pageHtml = await loadPage('candidate-detail.html');
            appContent.innerHTML = pageHtml;
            
            // 2. Fetch the candidate data
            const response = await fetch(`api/candidate/${candidateId}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch candidate data: ${response.statusText}`);
            }
            const candidateData = await response.json();

            // 3. Find, compile, and render the Handlebars template
            const templateSource = document.getElementById('candidate-detail-template').innerHTML;
            const template = Handlebars.compile(templateSource);
            const renderedHtml = template(candidateData);
            
            // 4. Inject the *rendered* HTML into its container
            const container = document.getElementById('candidate-detail-container');
            if (container) {
                container.innerHTML = renderedHtml;
            } else {
                console.error('Could not find #candidate-detail-container');
            }

            // 5. Add event listener to the file input
            const resumeViewerInput = document.getElementById('resume-viewer-input');
            if(resumeViewerInput) {
                resumeViewerInput.addEventListener('change', (event) => {
                    renderResume(event.target.files[0]);
                });
            }
        } catch (error) {
            console.error('Error initializing candidate detail page:', error);
            appContent.innerHTML = '<div class="container mt-4"><p class="text-danger">Error loading candidate details.</p></div>';
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
                // pdfjsLib is loaded globally in index.html
                pdfjsLib.getDocument(typedarray).promise.then(pdf => {
                    container.innerHTML = ''; // Clear previous content
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
                // mammoth is loaded globally in index.html
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
                    // This URL must match app.py
                    const response = await fetch('/upload-resumes/', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        const result = await response.json();
                        // FIX 3: Your API returns "processed_files", not "successful_uploads"
                        if(uploadStatus) uploadStatus.innerHTML = `<p class="text-success">Successfully processed ${result.processed_files.length} files.</p>`;
                        
                        setTimeout(() => {
                            window.location.hash = '#candidates';
                        }, 2000);
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
        // Must wait for filters to load *before* initializing Select2
        await initFilters();
        
        // Initialize Select2 (which is loaded in index.html)
        if ($.fn.select2) {
            $('#skills-filter').select2({
                placeholder: 'Select skills',
                width: '100%'
            });
        }
        
        initCandidatesDataTable(); // Initial data load

        // Attach event listeners
        // NOTE: Your backend at /api/candidates/table doesn't support filtering.
        // These listeners will just reload the full table.
        document.getElementById('exp-filter').addEventListener('change', initCandidatesDataTable);
        document.getElementById('skills-filter').addEventListener('change', initCandidatesDataTable);
        document.getElementById('city-filter').addEventListener('change', initCandidatesDataTable);
        
        document.getElementById('reset-filters-btn').addEventListener('click', () => {
            document.getElementById('exp-filter').value = '';
            document.getElementById('city-filter').value = '';
            // Use jQuery to reset Select2
            $('#skills-filter').val(null).trigger('change');
            // initCandidatesDataTable(); // The 'change' event on skills-filter will trigger this
        });
    }

    async function initFilters() {
        try {
            const response = await fetch('/api/filters');
            const filters = await response.json();

            const skillsFilter = document.getElementById('skills-filter');
            if (skillsFilter) {
                skillsFilter.innerHTML = ''; // Clear old options
                filters.skills.forEach(skill => {
                    const option = new Option(skill, skill);
                    skillsFilter.add(option);
                });
            }

            const cityFilter = document.getElementById('city-filter');
            if (cityFilter) {
                cityFilter.innerHTML = '<option value="">All</option>'; // Clear old options
                filters.cities.forEach(city => {
                    const option = new Option(city, city);
                    cityFilter.add(option);
                });
            }

        } catch (error) {
            console.error('Error initializing filters:', error);
        }
    }

    function initCandidatesDataTable() {
        const tableBody = document.getElementById('candidates-table-body');
        if (!tableBody) return;
        tableBody.innerHTML = '<tr><td colspan="8" class="text-center"><div class="loader"></div></td></tr>';

        // FIX 4: Your API endpoint is /api/candidates/table
        let apiUrl = '/api/candidates/table';
        
        // FIX 5: Your backend /api/candidates/table does not support filtering.
        // All query parameter logic has been removed.

        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                tableBody.innerHTML = '';
                data.forEach(candidate => {
                    // FIX 6: Changed keys to match your API response (e.g., total_exp, linkedin, skills, certifications)
                    const row = `
                        <tr>
                            <td><a href="#candidate?id=${candidate.id}">${candidate.name || 'N/A'}</a></td>
                            <td>${candidate.email || 'N/A'}</td>
                            <td>${candidate.phone || 'N/A'}</td>
                            <td><a href="${candidate.linkedin || '#'}" target="_blank">Profile</a></td>
                            <td>${candidate.total_exp || 'N/A'}</td>
                            <td>${candidate.city || 'N/A'}</td>
                            <td>${(candidate.skills || []).join(', ')}</td>
                            <td>${(candidate.certifications || []).join(', ')}</td>
                        </tr>
                    `;
                    tableBody.insertAdjacentHTML('beforeend', row);
                });
            })
            .catch(error => {
                console.error('Error fetching candidates:', error);
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Error loading candidates.</td></tr>';
            });
    }
});