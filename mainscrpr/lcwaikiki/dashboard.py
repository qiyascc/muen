from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

import json
from datetime import timedelta, datetime
from .models import ProductAvailableUrl, ProductNewUrl, ProductDeletedUrl


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'lcwaikiki/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current date
        now = timezone.now()
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        
        # Statistics for all time
        total_available = ProductAvailableUrl.objects.count()
        total_new = ProductNewUrl.objects.count()
        total_deleted = ProductDeletedUrl.objects.count()
        
        # Statistics for today
        today_available = ProductAvailableUrl.objects.filter(
            last_checking__gte=today
        ).count()
        today_new = ProductNewUrl.objects.filter(
            last_checking__gte=today
        ).count()
        today_deleted = ProductDeletedUrl.objects.filter(
            last_checking__gte=today
        ).count()
        
        # Statistics for this week
        week_available = ProductAvailableUrl.objects.filter(
            last_checking__gte=start_of_week
        ).count()
        week_new = ProductNewUrl.objects.filter(
            last_checking__gte=start_of_week
        ).count()
        week_deleted = ProductDeletedUrl.objects.filter(
            last_checking__gte=start_of_week
        ).count()
        
        # Statistics for this month
        month_available = ProductAvailableUrl.objects.filter(
            last_checking__gte=start_of_month
        ).count()
        month_new = ProductNewUrl.objects.filter(
            last_checking__gte=start_of_month
        ).count()
        month_deleted = ProductDeletedUrl.objects.filter(
            last_checking__gte=start_of_month
        ).count()
        
        # Chart data - last 30 days
        start_date = now - timedelta(days=30)
        
        # Get new products by day
        new_by_day = ProductNewUrl.objects.filter(
            last_checking__gte=start_date
        ).annotate(
            day=TruncDate('last_checking')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        # Get deleted products by day
        deleted_by_day = ProductDeletedUrl.objects.filter(
            last_checking__gte=start_date
        ).annotate(
            day=TruncDate('last_checking')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        # Generate data for the chart
        chart_dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
        chart_new = [0] * 31
        chart_deleted = [0] * 31
        
        # Map data to chart arrays
        for item in new_by_day:
            day_diff = (item['day'] - start_date.date()).days
            if 0 <= day_diff < 31:
                chart_new[day_diff] = item['count']
                
        for item in deleted_by_day:
            day_diff = (item['day'] - start_date.date()).days
            if 0 <= day_diff < 31:
                chart_deleted[day_diff] = item['count']
        
        # Add data to context
        context.update({
            'total_available': total_available,
            'total_new': total_new,
            'total_deleted': total_deleted,
            'today_available': today_available,
            'today_new': today_new,
            'today_deleted': today_deleted,
            'week_available': week_available,
            'week_new': week_new,
            'week_deleted': week_deleted,
            'month_available': month_available,
            'month_new': month_new,
            'month_deleted': month_deleted,
            'chart_dates': json.dumps(chart_dates),
            'chart_new': json.dumps(chart_new),
            'chart_deleted': json.dumps(chart_deleted),
        })
        
        # Add terminal output to context
        try:
            with open('logs/scraper.log', 'r') as f:
                log_lines = f.readlines()[-100:]  # Get last 100 lines
                context['terminal_output'] = ''.join(log_lines)
        except (FileNotFoundError, IOError):
            context['terminal_output'] = "Scraper log not found."
        
        return context