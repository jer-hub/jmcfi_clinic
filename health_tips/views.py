from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.conf import settings
import os
import uuid
from .models import HealthTip


@login_required
@require_POST
def upload_image(request):
    """Handle image upload for markdown editor"""
    if request.user.role != 'staff':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if 'image' not in request.FILES:
        return JsonResponse({'error': 'No image provided'}, status=400)
    
    image = request.FILES['image']
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if image.content_type not in allowed_types:
        return JsonResponse({'error': 'Invalid file type. Allowed: JPEG, PNG, GIF, WebP'}, status=400)
    
    # Validate file size (max 5MB)
    if image.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Maximum size is 5MB'}, status=400)
    
    # Generate unique filename
    ext = os.path.splitext(image.name)[1].lower()
    filename = f"health_tips/{uuid.uuid4().hex}{ext}"
    
    # Save file
    upload_path = os.path.join(settings.MEDIA_ROOT, filename)
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    
    with open(upload_path, 'wb+') as destination:
        for chunk in image.chunks():
            destination.write(chunk)
    
    # Return URL for EasyMDE
    image_url = f"{settings.MEDIA_URL}{filename}"
    return JsonResponse({'data': {'filePath': image_url}})


@login_required
def health_tips(request):
    """Display health tips - active tips for all, drafts visible to their creators"""
    if request.user.role in ['staff', 'doctor']:
        tips = HealthTip.objects.filter(
            Q(is_active=True) | Q(created_by=request.user)
        ).select_related('created_by').distinct()
    else:
        tips = HealthTip.objects.filter(is_active=True).select_related('created_by')
    
    category = request.GET.get('category')
    search = request.GET.get('search')
    
    if category:
        tips = tips.filter(category=category)
    
    if search:
        tips = tips.filter(
            Q(title__icontains=search) | 
            Q(content__icontains=search)
        )
    
    tips = tips.order_by('-created_at')
    
    paginator = Paginator(tips, 9)
    page = request.GET.get('page')
    tips = paginator.get_page(page)
    
    context = {
        'tips': tips,
        'categories': HealthTip.CATEGORY_CHOICES,
        'current_category': category,
        'search_query': search,
        'total_count': tips.paginator.count if tips else 0,
    }
    
    return render(request, 'health_tips/health_tips_list.html', context)


@login_required
def health_tip_detail(request, tip_id):
    """Display a single health tip's full content"""
    # Allow viewing active tips by anyone, drafts only by their creators
    if request.user.role in ['staff', 'doctor']:
        health_tip = get_object_or_404(
            HealthTip.objects.select_related('created_by'),
            Q(id=tip_id) & (Q(is_active=True) | Q(created_by=request.user))
        )
    else:
        health_tip = get_object_or_404(
            HealthTip.objects.select_related('created_by'),
            id=tip_id,
            is_active=True
        )
    
    # Get related tips in the same category (excluding current one)
    related_tips = HealthTip.objects.filter(
        category=health_tip.category,
        is_active=True
    ).exclude(id=tip_id).order_by('-created_at')[:3]
    
    context = {
        'tip': health_tip,
        'related_tips': related_tips,
    }
    
    return render(request, 'health_tips/health_tip_detail.html', context)


@login_required
def create_health_tip(request):
    """Create a new health tip - staff only"""
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can create health tips')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category = request.POST.get('category', '').strip()
        status = request.POST.get('status', 'published')
        
        # Validation
        errors = []
        if not title:
            errors.append('Title is required')
        elif len(title) > 200:
            errors.append('Title must be less than 200 characters')
        
        if not content:
            errors.append('Content is required')
        elif len(content) < 50:
            errors.append('Content must be at least 50 characters')
        
        if not category:
            errors.append('Category is required')
        elif category not in [choice[0] for choice in HealthTip.CATEGORY_CHOICES]:
            errors.append('Invalid category selected')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'health_tips/create_health_tip.html', {
                'title': title,
                'content': content,
                'category': category,
            })
        
        # Create health tip
        health_tip = HealthTip.objects.create(
            title=title,
            content=content,
            category=category,
            created_by=request.user,
            is_active=(status == 'published')
        )
        
        if status == 'published':
            messages.success(request, f'Health tip "{title}" has been published successfully!')
        else:
            messages.success(request, f'Health tip "{title}" has been saved as draft.')
        
        return redirect('health_tips:health_tips_list')
    
    return render(request, 'health_tips/create_health_tip.html')


@login_required
def edit_health_tip(request, tip_id):
    """Edit an existing health tip - staff only, own tips only"""
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can edit health tips')
        return redirect('core:dashboard')
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category = request.POST.get('category', '').strip()
        status = request.POST.get('status', 'published')
        
        # Validation
        errors = []
        if not title:
            errors.append('Title is required')
        elif len(title) > 200:
            errors.append('Title must be less than 200 characters')
        
        if not content:
            errors.append('Content is required')
        elif len(content) < 50:
            errors.append('Content must be at least 50 characters')
        
        if not category:
            errors.append('Category is required')
        elif category not in [choice[0] for choice in HealthTip.CATEGORY_CHOICES]:
            errors.append('Invalid category selected')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'health_tips/edit_health_tip.html', {
                'health_tip': health_tip,
                'title': title,
                'content': content,
                'category': category,
            })
        
        # Update health tip
        health_tip.title = title
        health_tip.content = content
        health_tip.category = category
        health_tip.is_active = (status == 'published')
        health_tip.save()
        
        if status == 'published':
            messages.success(request, f'Health tip "{title}" has been updated and published successfully!')
        else:
            messages.success(request, f'Health tip "{title}" has been updated and saved as draft.')
        
        return redirect('health_tips:health_tips_list')
    
    return render(request, 'health_tips/edit_health_tip.html', {'health_tip': health_tip})


@login_required
def delete_health_tip(request, tip_id):
    """Delete a health tip - staff only, own tips only"""
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can delete health tips')
        return redirect('core:dashboard')
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        title = health_tip.title
        health_tip.delete()
        messages.success(request, f'Health tip "{title}" has been deleted successfully.')
        return redirect('health_tips:health_tips_list')
    
    return render(request, 'health_tips/delete_health_tip.html', {'health_tip': health_tip})


@login_required
def toggle_health_tip_status(request, tip_id):
    """Toggle the active status of a health tip - staff only"""
    if request.user.role != 'staff':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        health_tip.is_active = not health_tip.is_active
        health_tip.save()
        
        status_text = 'published' if health_tip.is_active else 'unpublished'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_active': health_tip.is_active,
                'status_text': status_text,
                'message': f'Health tip has been {status_text}'
            })
        messages.success(request, f'Health tip "{health_tip.title}" has been {status_text}.')
    
    return redirect('health_tips:health_tips_list')
