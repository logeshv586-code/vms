import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models

# Determine paths
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BACKEND_DIR, "data", "graffiti_vandalism")
MODEL_SAVE_PATH = os.path.join(BACKEND_DIR, "models", "detections", "graffiti_and_vandalism", "graffiti_vandalism_model.pt")

def train_model(epochs=1, batch_size=2, learning_rate=0.001):
    print("=== Starting Graffiti & Vandalism Training Pipeline ===")
    
    # 1. Image Transformations & Data Augmentation
    data_transforms = {
        'train': transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    }

    # 2. Loading datasets using ImageFolder
    train_dir = os.path.join(DATA_DIR, "train")
    val_dir = os.path.join(DATA_DIR, "val")
    
    if not os.path.exists(train_dir) or not os.path.exists(val_dir):
        print("[ERROR] Dataset splits not found. Please run dataset_downloader.py first.")
        return False
        
    print(f"Loading data from: {DATA_DIR}")
    image_datasets = {
        'train': datasets.ImageFolder(train_dir, data_transforms['train']),
        'val': datasets.ImageFolder(val_dir, data_transforms['val'])
    }
    
    dataloaders = {
        'train': DataLoader(image_datasets['train'], batch_size=batch_size, shuffle=True, num_workers=0),
        'val': DataLoader(image_datasets['val'], batch_size=batch_size, shuffle=False, num_workers=0)
    }
    
    dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}
    class_names = image_datasets['train'].classes
    print(f"Classes found: {class_names}")
    print(f"Train size: {dataset_sizes['train']} images, Val size: {dataset_sizes['val']} images")

    # 3. Model instantiation (ResNet18 transfer learning)
    print("Initializing ResNet18 model...")
    # Using weights=None to avoid downloading large pretrained weights during local verification
    model = models.resnet18(weights=None)
    num_ftrs = model.fc.in_features
    # 3 classes: graffiti, vandalism, normal
    model.fc = nn.Linear(num_ftrs, len(class_names))
    
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    print(f"Running training on: {device}")

    # 4. Loss Function & Optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # 5. Training loop
    for epoch in range(epochs):
        print(f"\nEpoch {epoch+1}/{epochs}")
        print("-" * 10)
        
        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()
            else:
                model.eval()
                
            running_loss = 0.0
            running_corrects = 0
            
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)
                
                optimizer.zero_grad()
                
                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)
                    
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()
                        
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)
                
            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]
            
            print(f"{phase.capitalize()} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}")
            
    # Save the trained model checkpoint
    os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
    torch.save(model.state_dict(), MODEL_SAVE_PATH)
    print(f"\n[SUCCESS] Model checkpoint saved at: {MODEL_SAVE_PATH}")
    return True

if __name__ == "__main__":
    train_model(epochs=1, batch_size=2)
