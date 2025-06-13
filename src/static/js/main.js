// Main JavaScript for the finance tracker application

document.addEventListener('DOMContentLoaded', function() {
    // Set default date range (current year)
    const today = new Date();
    const startOfYear = new Date(today.getFullYear(), 0, 1);
    
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    if (startDateInput && endDateInput) {
        // Format dates as YYYY-MM-DD
        startDateInput.value = formatDate(startOfYear);
        endDateInput.value = formatDate(today);
        
        // Add event listener for the reset button
        document.getElementById('resetFilter').addEventListener('click', function() {
            startDateInput.value = formatDate(startOfYear);
            endDateInput.value = formatDate(today);
            
            // If we're on a page with loadData function, reload the data
            if (typeof loadData === 'function') {
                loadData();
            }
        });
        
        // Add event listener for the form submission
        document.getElementById('dateRangeForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            // If we're on a page with loadData function, reload the data
            if (typeof loadData === 'function') {
                loadData();
            }
        });
    }
    
    // Initialize any tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Helper function to format date as YYYY-MM-DD
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Helper function to get current date range filter
function getDateRangeParams() {
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    
    return {
        start_date: startDate,
        end_date: endDate
    };
}

// Helper function to format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'EGP'
    }).format(amount);
}

// Helper function to format percentage
function formatPercentage(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value / 100);
}

// Helper function to create a chart
function createChart(canvasId, type, labels, datasets, options = {}) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    // Default options
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false
    };
    
    // Merge default options with provided options
    const chartOptions = { ...defaultOptions, ...options };
    
    return new Chart(ctx, {
        type: type,
        data: {
            labels: labels,
            datasets: datasets
        },
        options: chartOptions
    });
}

// Helper function to generate random colors for charts
function generateRandomColors(count) {
    const colors = [];
    for (let i = 0; i < count; i++) {
        const hue = (i * 137) % 360; // Use golden angle to get evenly distributed colors
        colors.push(`hsl(${hue}, 70%, 60%)`);
    }
    return colors;
}

// Helper function to show loading spinner
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="d-flex justify-content-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    }
}

// Helper function to show error message
function showError(elementId, message) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `<div class="alert alert-danger" role="alert">${message}</div>`;
    }
}
