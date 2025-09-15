import { Component, Input, OnInit, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-viewer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './viewer.component.html',
  styleUrl: './viewer.component.scss'
})
export class ViewerComponent implements OnInit {
  @Input() modelPath: string = '';
  
  iframeSrc: SafeResourceUrl | null = null;
  isLoading: boolean = false;
  error: string = '';

  constructor(private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    if (this.modelPath) {
      this.loadModel(this.modelPath);
    }
  }

  ngOnChanges(): void {
    if (this.modelPath) {
      this.loadModel(this.modelPath);
    }
  }

  loadModel(path: string): void {
    this.isLoading = true;
    this.error = '';
    
    // For now, just show a placeholder
    // In production, this would call the Python renderer to generate HTML
    console.log('Loading 3D model:', path);
    
    // Simulate loading
    setTimeout(() => {
      this.isLoading = false;
    }, 1000);
  }
}