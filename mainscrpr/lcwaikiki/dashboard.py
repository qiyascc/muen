from django.db.models import Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from .models import ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'lcwaikiki/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current date and relevant time periods
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        year_ago = today - timedelta(days=365)
        
        # Get statistics for all time
        context['total_available'] = ProductAvailableUrl.objects.count()
        context['total_deleted'] = ProductDeletedUrl.objects.count()
        context['total_new'] = ProductNewUrl.objects.count()
        
        # Get statistics for today
        context['today_available'] = ProductAvailableUrl.objects.filter(
            last_checking__gte=today
        ).count()
        context['today_deleted'] = ProductDeletedUrl.objects.filter(
            last_checking__gte=today
        ).count()
        context['today_new'] = ProductNewUrl.objects.filter(
            last_checking__gte=today
        ).count()
        
        # Get statistics for past week
        context['week_available'] = ProductAvailableUrl.objects.filter(
            last_checking__gte=week_ago
        ).count()
        context['week_deleted'] = ProductDeletedUrl.objects.filter(
            last_checking__gte=week_ago
        ).count()
        context['week_new'] = ProductNewUrl.objects.filter(
            last_checking__gte=week_ago
        ).count()
        
        # Get statistics for past month
        context['month_available'] = ProductAvailableUrl.objects.filter(
            last_checking__gte=month_ago
        ).count()
        context['month_deleted'] = ProductDeletedUrl.objects.filter(
            last_checking__gte=month_ago
        ).count()
        context['month_new'] = ProductNewUrl.objects.filter(
            last_checking__gte=month_ago
        ).count()
        
        # Chart data for new and deleted products over past 30 days
        daily_new = (
            ProductNewUrl.objects.filter(last_checking__gte=month_ago)
            .annotate(date=TruncDay("last_checking"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        
        daily_deleted = (
            ProductDeletedUrl.objects.filter(last_checking__gte=month_ago)
            .annotate(date=TruncDay("last_checking"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        
        # Format chart data for JavaScript
        chart_dates = []
        chart_new = []
        chart_deleted = []
        
        # Create a map for easy access by date
        new_by_date = {x['date'].strftime('%Y-%m-%d'): x['count'] for x in daily_new}
        deleted_by_date = {x['date'].strftime('%Y-%m-%d'): x['count'] for x in daily_deleted}
        
        # Generate a list of the past 30 days
        for i in range(30, -1, -1):
            date = (now - timedelta(days=i)).date()
            date_str = date.strftime('%Y-%m-%d')
            chart_dates.append(date_str)
            chart_new.append(new_by_date.get(date_str, 0))
            chart_deleted.append(deleted_by_date.get(date_str, 0))
        
        context['chart_dates'] = chart_dates
        context['chart_new'] = chart_new
        context['chart_deleted'] = chart_deleted
        
        # Log File Path
        import os
        log_path = os.path.join('logs', 'scraper.log')
        context['log_path'] = log_path
        
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                # Get last 50 lines
                log_content = f.readlines()[-50:]
                context['terminal_output'] = ''.join(log_content)
        else:
            # Create logs directory
            os.makedirs('logs', exist_ok=True)
            context['terminal_output'] = 'No logs available yet.'
        
        return context