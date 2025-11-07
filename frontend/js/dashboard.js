
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

async function initDashboard() {
    try {
        const response = await fetch('/api/analytics');
        const analyticsData = await response.json();

        renderSkillsChart(analyticsData.skill_distribution);
        renderExperienceChart(analyticsData.experience_distribution);

    } catch (error) {
        console.error('Error initializing dashboard:', error);
    }
}

function renderSkillsChart(skillData) {
    const ctx = document.getElementById('skills-chart').getContext('2d');
    new Chart(ctx, {
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
        options: {
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function renderExperienceChart(experienceData) {
    const ctx = document.getElementById('experience-chart').getContext('2d');
    new Chart(ctx, {
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
