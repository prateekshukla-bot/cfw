from django.shortcuts import render, redirect
from django.contrib import messages
from .models import User

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        # Check credentials
        try:
            user = User.objects.get(username=username, password=password)
            request.session['user_id'] = user.id  # Save user session
            return redirect('landing_page')  # Redirect to landing page
        except User.DoesNotExist:
            messages.error(request, "Invalid username or password.")
    
    return render(request, 'login.html')

def landing_page(request):
    if 'user_id' not in request.session:  # Check if user is logged in
        return redirect('login')  # Redirect to login page
    
    return render(request, 'landing_page.html')

from django.shortcuts import render, redirect

# Other imports and views

def logout_view(request):
    request.session.flush()  # Clear all session data
    return redirect('login')  # Redirect to login page
