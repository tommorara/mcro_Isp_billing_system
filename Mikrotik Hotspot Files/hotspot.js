function validatePhone(phone) {
    const phoneRegex = /^\+254[0-9]{9}$/;
    return phoneRegex.test(phone);
}

function displayPaymentStatus(message, isError = false) {
    const statusDiv = document.getElementById('payment-status');
    statusDiv.textContent = message;
    statusDiv.className = 'payment-status' + (isError ? ' error' : '');
    statusDiv.style.display = 'block';
    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 5000);
}

function autoConnect(username, password) {
    const loginForm = document.getElementById('hotspotLoginForm');
    document.getElementById('loginUsername').value = username;
    document.getElementById('loginPassword').value = password;
    loginForm.submit();
}

// Fetch and display packages
fetch('https://yourdomain.com/api/hotspot/plans/')
    .then(response => response.json())
    .then(data => {
        const packagesDiv = document.getElementById('packages');
        data.forEach(pkg => {
            const card = document.createElement('div');
            card.className = 'package-card';
            card.innerHTML = `
                <h3>${pkg.name}</h3>
                <p>Price: KSH ${pkg.price}</p>
                <p>Speed: ${pkg.download_bandwidth}Mbps down/${pkg.upload_bandwidth}Mbps up</p>
                <p>Duration: ${
                    pkg.duration_minutes ? `${pkg.duration_minutes} minutes` :
                    pkg.duration_hours ? `${pkg.duration_hours} hours` :
                    `${pkg.duration_days} days`
                }</p>
                <button onclick="initiatePayment(${pkg.id})">Buy Now</button>
            `;
            packagesDiv.appendChild(card);
        });
    })
    .catch(error => {
        console.error('Error fetching plans:', error);
        displayPaymentStatus('Failed to load plans. Please try again.', true);
    });

// Initiate M-Pesa payment
function initiatePayment(packageId) {
    const phone = document.getElementById('phone').value;
    if (!validatePhone(phone)) {
        displayPaymentStatus('Please enter a valid phone number (e.g., +254123456789)', true);
        return;
    }

    displayPaymentStatus('Initiating payment... Please wait.');
    fetch('https://yourdomain.com/api/hotspot/pay/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ package_id: packageId, phone: phone }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            displayPaymentStatus(data.error, true);
        } else if (data.status === 'pending') {
            displayPaymentStatus('Please complete the M-Pesa STK Push on your phone.');
            // Poll for payment status
            const checkStatus = setInterval(() => {
                fetch(`https://yourdomain.com/api/hotspot/pay/?transaction_id=${data.transaction_id}`)
                    .then(res => res.json())
                    .then(statusData => {
                        if (statusData.status === 'success') {
                            clearInterval(checkStatus);
                            const loginMethod = statusData.login_method;
                            const username = statusData.username;
                            const password = statusData.password;
                            let displayText = `Payment successful! `;
                            if (loginMethod === 'VOUCHER') {
                                displayText += `Voucher Code: ${username}`;
                            } else if (loginMethod === 'TRANSACTION') {
                                displayText += `Transaction ID: ${username}`;
                            } else {
                                displayText += `Username: ${username}`;
                            }
                            displayText += `, Password: ${password}`;
                            displayPaymentStatus(displayText);
                            setTimeout(() => autoConnect(username, password), 5000);
                        } else if (statusData.status === 'failed') {
                            clearInterval(checkStatus);
                            displayPaymentStatus('Payment failed. Please try again.', true);
                        }
                    });
            }, 5000);
        }
    })
    .catch(error => {
        console.error('Error initiating payment:', error);
        displayPaymentStatus('Payment initiation failed. Please try again.', true);
    });
}