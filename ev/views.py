from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.http import JsonResponse
from datetime import datetime
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Station, UserProfile, ChargingSession, UserPreferences
import random
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
import json


@login_required(login_url='/login/')
def home(request):
    # Get recently used stations (last 5)
    recent_stations = Station.objects.filter(
        chargingsession__user=request.user
    ).order_by('-chargingsession__start_time').distinct()[:5]

    # If no recent stations, show 5 random stations
    if not recent_stations:
        recent_stations = Station.objects.order_by('?')[:5]

    return render(request, 'ev/home.html', {
        'stations': recent_stations,
    })

def station(request):
    state = request.GET.get("state", "")
    city = request.GET.get("city", "")

    # Fetch all stations
    stations = Station.objects.all()

    # Apply filters if selected
    if state:
        stations = stations.filter(state__iexact=state)
    if city:
        stations = stations.filter(city__iexact=city)

    # Get all distinct states
    states = Station.objects.values_list("state", flat=True).distinct()

    # Get distinct cities
    if state:
        cities = list(Station.objects.filter(state__iexact=state).values_list("city", flat=True).distinct())
    else:
        cities = []

    context = {
        "stations": stations,
        "states": states,
        "cities": cities,
        "selected_state": state,
        "selected_city": city,
    }
    return render(request, "ev/station.html", context)

# Create your views here.

def get_server_time(request):
    now = datetime.now()  # ✅ Get current time
    return JsonResponse({"server_time": now.strftime("%Y-%m-%d %H:%M:%S")})  # ✅ Return formatted time

def server_info(request):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # ✅ Get formatted server time
    # Generate random CPU temperature between 30-80     
    voltage_info = random.uniform(110.0, 115.0)
    current_info = random.uniform(30.0, 80.0)
    return JsonResponse({
        "server_time": now, 
        "voltage_info": round(voltage_info, 1),
        "current_info": round(current_info, 1),
        # Round to 1 decimal place
    })

def register(request):
    if request.method == "POST":
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password == confirm_password:
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists")
            elif User.objects.filter(email=email).exists():
                messages.error(request, "Email already registered")
            else:
                user = User.objects.create_user(username=username, email=email, password=password)
                user.save()
                messages.success(request, "Account created successfully! Please log in.")
                return redirect('login')
        else:
            messages.error(request, "Passwords do not match")

    return render(request, 'ev/register.html')

def user_login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')  # Change 'home' to your dashboard page
        else:
            messages.error(request, "Invalid username or password")
    
    return render(request, 'ev/login.html')

def user_logout(request):
    logout(request)
    return redirect('login')

def ev_station_list(request):
    state = request.GET.get("state", "")
    city = request.GET.get("city", "")

    # Fetch all EV stations
    stations = Station.objects.all()

    # Apply filters if selected
    if state:
        stations = stations.filter(state__iexact=state)
    if city:
        stations = stations.filter(city__iexact=city)

    # Get all distinct states
    states = Station.objects.values_list("state", flat=True).distinct()

    # Get distinct cities
    if state:
        cities = list(Station.objects.filter(state__iexact=state).values_list("city", flat=True).distinct())
    else:
        cities = list(Station.objects.values_list("city", flat=True).distinct())

    print(f"Selected state: {state}, Cities: {cities}")  # Debugging

    return render(request, "ev/station.html", {
        "stations": stations,
        "states": states,
        "cities": cities,  # Now dynamically updates
        "selected_state": state,
        "selected_city": city,
    })

# API to fetch cities dynamically
def get_cities(request):
    state = request.GET.get("state", "")
    if state:
        cities = list(Station.objects.filter(state__iexact=state).values_list("city", flat=True).distinct())
    else:
        cities = []
    
    return JsonResponse({"cities": cities})

@login_required
def user_profile(request):
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get recent charging sessions
    recent_sessions = ChargingSession.objects.filter(user=request.user).order_by('-start_time')[:5]
    
    # Get the most recent station used
    recent_station = None
    if recent_sessions.exists():
        recent_station = recent_sessions.first().station
    
    context = {
        'profile': profile,
        'recent_sessions': recent_sessions,
        'recent_station': recent_station,
    }
    return render(request, 'ev/user.html', context)

@login_required
@require_POST
def update_profile(request):
    profile = request.user.profile
    profile.save()
    messages.success(request, 'Profile updated successfully!')
    return redirect('user_profile')

@login_required
@require_POST
def update_preferences(request):
    preferences = request.user.preferences
    preferences.preferred_station_type = request.POST.get('preferred_station_type', 'BOTH')
    preferences.low_balance_alert = Decimal(request.POST.get('low_balance_alert', 20.00))
    preferences.save()
    messages.success(request, 'Preferences updated successfully!')
    return redirect('user_profile')

@login_required
def recharge_account(request):
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount greater than 0')
                return redirect('recharge_account')
            
            # Get or create user profile
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            # Update balance
            profile.account_balance += amount
            profile.save()
            
            messages.success(request, f'Successfully recharged ₹{amount:.2f}')
            return redirect('user_profile')
            
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount entered')
            return redirect('recharge_account')
    
    return render(request, 'ev/recharge_account.html')

@login_required
def start_charging(request, station_id):
    try:
        station = Station.objects.get(id=station_id, is_available=True)
        profile = request.user.profile
        
        # Check if user has sufficient balance
        if profile.account_balance < Decimal('10.00'):
            messages.error(request, 'Insufficient balance. Please recharge your account.')
            return redirect('station')
        
        # Create new charging session
        session = ChargingSession.objects.create(
            user=request.user,
            station=station,
            start_time=timezone.now()
        )
        
        # Update station availability
        station.is_available = False
        station.save()
        
        messages.success(request, f'Charging started at {station.name}')
        return redirect('home')
        
    except Station.DoesNotExist:
        messages.error(request, 'Station not available')
        return redirect('station')

@login_required
def stop_charging(request, session_id):
    try:
        session = ChargingSession.objects.get(id=session_id, user=request.user, status='in_progress')
        profile = request.user.profile
        
        # Calculate energy consumed and cost
        duration = session.duration()
        hours = duration.total_seconds() / 3600
        energy_consumed = Decimal(str(hours * 7.2))  # Assuming 7.2kW charging rate
        cost = energy_consumed * Decimal('0.15')  # Assuming $0.15 per kWh
        
        # Update session
        session.end_time = timezone.now()
        session.energy_consumed = energy_consumed
        session.cost = cost
        session.status = 'completed'
        session.save()
        
        # Update station availability
        session.station.is_available = True
        session.station.save()
        
        # Update user profile
        profile.account_balance -= cost
        profile.total_sessions += 1
        profile.total_energy_consumed += energy_consumed
        profile.total_amount_spent += cost
        profile.save()
        
        messages.success(request, f'Charging completed. Energy consumed: {energy_consumed:.2f} kWh, Cost: ${cost:.2f}')
        return redirect('user_profile')
        
    except ChargingSession.DoesNotExist:
        messages.error(request, 'Invalid charging session')
        return redirect('user_profile')

@csrf_exempt
@require_POST
def update_charging_status(request):
    try:
        data = json.loads(request.body)
        station_id = data.get('station_id')
        station_name = data.get('station_name')
        station_location = data.get('station_location')
        is_charging = data.get('is_charging')
        
        # Here you would typically update your database
        # For now, we'll just return a success response
        response_data = {
            'status': 'success',
            'message': f'Charging status updated for {station_name}',
            'data': {
                'station_id': station_id,
                'station_name': station_name,
                'station_location': station_location,
                'is_charging': is_charging
            }
        }
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

def test_api(request):
    stations = Station.objects.all().order_by('name')
    return render(request, 'ev/test_api.html', {'stations': stations})
