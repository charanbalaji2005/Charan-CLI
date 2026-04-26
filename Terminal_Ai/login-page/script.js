document.getElementById('login-form').addEventListener('submit', function(event) {
    event.preventDefault();
    
    const username = event.target.username.value;
    const password = event.target.password.value;
    const message = document.getElementById('message');

    if (username === 'admin' && password === 'password') {
        message.textContent = 'Login successful!';
        message.style.color = 'green';
    } else {
        message.textContent = 'Invalid username or password.';
        message.style.color = 'red';
    }
});
