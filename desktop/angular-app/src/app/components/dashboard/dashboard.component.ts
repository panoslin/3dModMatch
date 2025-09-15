import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';
import { BlankManagerComponent } from '../blank-manager/blank-manager.component';
import { MatchingComponent } from '../matching/matching.component';
import { HistoryComponent } from '../history/history.component';
import { ViewerComponent } from '../viewer/viewer.component';
import { ElectronService } from '../../services/electron.service';
import { interval, Subscription } from 'rxjs';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    ButtonModule,
    TooltipModule,
    BlankManagerComponent,
    MatchingComponent,
    HistoryComponent,
    ViewerComponent
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit, OnDestroy {
  activeView: string = 'blanks';
  showViewer: boolean = true;
  currentModelPath: string = '';
  version: string = '1.0.0';
  isConnected: boolean = false;
  activeTask: string = '';
  memoryUsage: number = 0;
  currentTime: string = '';
  
  stats = {
    totalBlanks: 0,
    totalModels: 0,
    totalMatches: 0,
    successfulMatches: 0,
    totalPassedResults: 0
  };

  private timeSubscription?: Subscription;
  private statsSubscription?: Subscription;

  constructor(private electronService: ElectronService) {}

  ngOnInit(): void {
    this.initializeApp();
    this.startTimeUpdate();
    this.loadStatistics();
    this.checkConnection();
  }

  ngOnDestroy(): void {
    if (this.timeSubscription) {
      this.timeSubscription.unsubscribe();
    }
    if (this.statsSubscription) {
      this.statsSubscription.unsubscribe();
    }
  }

  async initializeApp(): Promise<void> {
    if (this.electronService.isElectron()) {
      try {
        this.version = await this.electronService.getVersion();
        this.isConnected = true;
      } catch (error) {
        console.error('Failed to get version:', error);
      }
    } else {
      console.log('Running in web mode');
    }
  }

  setActiveView(view: string): void {
    this.activeView = view;
    
    // Show viewer for certain views
    if (view === 'matching' || view === 'blanks') {
      this.showViewer = true;
    }
  }

  toggleViewer(): void {
    this.showViewer = !this.showViewer;
  }

  showStatistics(): void {
    this.activeView = 'statistics';
    this.loadStatistics();
  }

  async loadStatistics(): Promise<void> {
    if (!this.electronService.isElectron()) return;
    
    try {
      const api = this.electronService.getAPI();
      if (api) {
        this.stats = await api.database.getStatistics();
      }
    } catch (error) {
      console.error('Failed to load statistics:', error);
    }
  }

  async checkConnection(): Promise<void> {
    if (!this.electronService.isElectron()) {
      this.isConnected = false;
      return;
    }

    try {
      const api = this.electronService.getAPI();
      if (api) {
        // Test database connection
        await api.database.getStatistics();
        this.isConnected = true;
      }
    } catch (error) {
      this.isConnected = false;
      console.error('Connection check failed:', error);
    }
  }

  private startTimeUpdate(): void {
    // Update time every second
    this.timeSubscription = interval(1000).subscribe(() => {
      const now = new Date();
      this.currentTime = now.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    });

    // Update memory usage every 5 seconds
    this.statsSubscription = interval(5000).subscribe(() => {
      this.updateMemoryUsage();
    });
  }

  private updateMemoryUsage(): void {
    if (typeof window !== 'undefined' && 'performance' in window) {
      const perf = (window.performance as any);
      if (perf.memory) {
        this.memoryUsage = Math.round(perf.memory.usedJSHeapSize / 1048576);
      }
    }
  }
}