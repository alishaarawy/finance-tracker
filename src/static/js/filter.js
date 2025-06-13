function getDateRangeParams() {
    const startDateInput = document.getElementById('start_date')?.value || '';
    const endDateInput = document.getElementById('end_date')?.value || '';
    const defaultStart = new Date();
    defaultStart.setFullYear(defaultStart.getFullYear() - 1); // Default to 1 year ago
    const defaultEnd = new Date();
    return {
        start_date: startDateInput || defaultStart.toISOString().split('T')[0],
        end_date: endDateInput || defaultEnd.toISOString().split('T')[0]
    };
}

function handleFilterSubmit(event) {
    event.preventDefault();
    const dateParams = getDateRangeParams();
    const queryString = new URLSearchParams({
        start_date: dateParams.start_date,
        end_date: dateParams.end_date
    }).toString();

    let currentPath = window.location.pathname;
    if (currentPath.endsWith('/')) {
        currentPath = currentPath.slice(0, -1);
    }

    // Map paths to their respective load functions
    const pageLoadFunctions = {
        '/expense': window.loadExpenseData,
        '/income': window.loadIncomeData,
        '/gold/transactions': window.loadGoldData,
        '/gold/prices': window.loadGoldPriceData,
        '/exchange': window.loadExchangeData,
        '/inflation': window.loadInflationData,
        '/': window.loadDashboardData,
        '/expense/item_analysis': window.loadItemAnalysisData
    };

    const loadFunction = pageLoadFunctions[currentPath];
    if (loadFunction && typeof loadFunction === 'function') {
        loadFunction(queryString); // Call client-side data refresh
    } else {
        // Fallback to server-side redirect
        console.warn(`No valid load function found for path: ${currentPath}`);
        window.location.href = `${currentPath}?${queryString}`;
    }
}

function resetFilter() {
    document.getElementById('start_date').value = '';
    document.getElementById('end_date').value = '';
    handleFilterSubmit(new Event('submit'));
}

document.addEventListener('DOMContentLoaded', function() {
    const filterForm = document.getElementById('dateFilterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', handleFilterSubmit);
    }

    const resetFilterBtn = document.getElementById('resetFilter');
    if (resetFilterBtn) {
        resetFilterBtn.addEventListener('click', resetFilter);
    }
});