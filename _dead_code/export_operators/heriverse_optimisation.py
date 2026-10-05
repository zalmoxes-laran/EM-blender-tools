"""Q5 of MICRO-IL-PANNELLO-DICE-IL-VERO (E.D., 5 Oct 2026): the Heriverse
exporter's optimisation of its own, out of `export_operators/heriverse/
operator.py`. Methods of `HERIVERSE_OT_export` kept here as they were; nothing
calls them. The preparation is «Prepare for a use…» in Asset versions."""


class _RemovedFromHeriverseExport:
    def compress_textures_in_folder(self, folder_path, scene):
        """
        Compresses all textures in a folder and its subfolders in a single pass.
        
        Args:
            folder_path (str): Path to the folder containing textures to compress
            scene (bpy.types.Scene): Blender scene containing compression settings
        """
        if not scene.heriverse_enable_compression:
            return
            
        # Import required libraries
        import os
        
        try:
            # Import Pillow
            from PIL import Image
            
            em_log(f"\n=== Compressing all textures in {folder_path} ===", "INFO")
            
            # Settings
            max_res = scene.heriverse_texture_max_res
            quality = scene.heriverse_texture_quality
            
            # Track statistics
            total_processed = 0
            total_resized = 0
            total_size_before = 0
            total_size_after = 0
            
            # Process all image files in the directory and subdirectories
            for root, dirs, files in os.walk(folder_path):
                for filename in files:
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tga')):
                        file_path = os.path.join(root, filename)
                        
                        try:
                            # Get original file size
                            file_size_before = os.path.getsize(file_path)
                            total_size_before += file_size_before
                            
                            # Open the image with Pillow
                            img = Image.open(file_path)
                            
                            # Check if resizing is needed
                            width, height = img.size
                            needs_resize = max(width, height) > max_res
                            
                            if needs_resize:
                                # Calculate new dimensions while preserving aspect ratio
                                if width > height:
                                    new_width = max_res
                                    new_height = int(height * (max_res / width))
                                else:
                                    new_height = max_res
                                    new_width = int(width * (max_res / height))
                                    
                                # Use high-quality resampling
                                img = img.resize((new_width, new_height), Image.LANCZOS)
                                total_resized += 1
                            
                            # Save with appropriate format and compression
                            if img.mode == 'RGBA' and filename.lower().endswith('.png'):
                                # Save as PNG with compression for transparency
                                img.save(file_path, 'PNG', optimize=True)
                            else:
                                # Convert to RGB if needed and save as JPEG
                                if img.mode != 'RGB':
                                    img = img.convert('RGB')
                                img.save(file_path, 'JPEG', quality=quality, optimize=True)
                            
                            # Get new file size
                            file_size_after = os.path.getsize(file_path)
                            total_size_after += file_size_after
                            
                            total_processed += 1
                            
                        except Exception as e:
                            em_log(f"Error processing {filename}: {str(e)}", "ERROR")
            
            # Calculate size reduction
            size_reduction_mb = (total_size_before - total_size_after) / (1024 * 1024)
            percentage_reduction = ((total_size_before - total_size_after) / total_size_before * 100) if total_size_before > 0 else 0
            
            em_log(f"Texture compression summary:", "DEBUG")
            em_log(f"- Total textures processed: {total_processed}", "DEBUG")
            em_log(f"- Textures resized: {total_resized}", "DEBUG")
            em_log(f"- Size before: {total_size_before / (1024 * 1024):.2f} MB", "DEBUG")
            em_log(f"- Size after: {total_size_after / (1024 * 1024):.2f} MB", "DEBUG")
            em_log(f"- Size reduction: {size_reduction_mb:.2f} MB ({percentage_reduction:.1f}%)", "DEBUG")
            
            return total_processed
            
        except ImportError:
            self._saltato("texture compression",
                          "Pillow is not installed", avvisa=True)
            return 0
        except Exception as e:
            em_log(f"Error during texture compression: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
            return 0

    # Modifica alla funzione export_rm per supportare GPU instances

    def export_textures(self, obj, textures_dir, context):
        """Export textures for an object with optional compression"""
        scene = context.scene
        
        for mat_slot in obj.material_slots:
            if mat_slot.material and mat_slot.material.use_nodes:
                for node in mat_slot.material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        try:
                            image = node.image
                            if image.packed_file:
                                image_path = os.path.join(textures_dir, clean_filename(image.name))
                                em_log(f"Exporting packed texture: {image.name}", "DEBUG")
                                
                                # If compression is enabled
                                if scene.heriverse_enable_compression:
                                    # Store original settings
                                    original_format = scene.render.image_settings.file_format
                                    original_quality = scene.render.image_settings.quality
                                    
                                    # Apply compression settings
                                    scene.render.image_settings.file_format = 'JPEG'
                                    scene.render.image_settings.quality = scene.heriverse_texture_quality
                                    
                                    # If image needs scaling
                                    needs_scaling = (image.size[0] > scene.heriverse_texture_max_res or 
                                                    image.size[1] > scene.heriverse_texture_max_res)
                                    
                                    if needs_scaling:
                                        # Create a temporary copy and scale it
                                        temp_image = image.copy()
                                        max_dim = max(temp_image.size[0], temp_image.size[1])
                                        scale_factor = scene.heriverse_texture_max_res / max_dim
                                        new_width = int(temp_image.size[0] * scale_factor)
                                        new_height = int(temp_image.size[1] * scale_factor)
                                        temp_image.scale(new_width, new_height)
                                        temp_image.save_render(image_path)
                                        bpy.data.images.remove(temp_image)
                                    else:
                                        # Just save with compression settings
                                        image.save_render(image_path)
                                        
                                    # Restore original settings
                                    scene.render.image_settings.file_format = original_format
                                    scene.render.image_settings.quality = original_quality
                                else:
                                    # Export without compression
                                    image.save_render(image_path)
                            elif image.filepath:
                                src_path = bpy.path.abspath(image.filepath)
                                if os.path.exists(src_path):
                                    dst_path = os.path.join(textures_dir, clean_filename(os.path.basename(image.filepath)))
                                    em_log(f"Copying external texture: {os.path.basename(image.filepath)}", "DEBUG")
                                    
                                    # If compression is enabled, load and process the image
                                    if scene.heriverse_enable_compression:
                                        # Create a temporary image
                                        temp_image = bpy.data.images.load(src_path)
                                        
                                        # Store original settings
                                        original_format = scene.render.image_settings.file_format
                                        original_quality = scene.render.image_settings.quality
                                        
                                        # Apply compression settings
                                        scene.render.image_settings.file_format = 'JPEG'
                                        scene.render.image_settings.quality = scene.heriverse_texture_quality
                                        
                                        # Check if scaling is needed
                                        needs_scaling = (temp_image.size[0] > scene.heriverse_texture_max_res or 
                                                        temp_image.size[1] > scene.heriverse_texture_max_res)
                                        
                                        if needs_scaling:
                                            max_dim = max(temp_image.size[0], temp_image.size[1])
                                            scale_factor = scene.heriverse_texture_max_res / max_dim
                                            new_width = int(temp_image.size[0] * scale_factor)
                                            new_height = int(temp_image.size[1] * scale_factor)
                                            temp_image.scale(new_width, new_height)
                                        
                                        # Save with compression
                                        temp_image.save_render(dst_path)
                                        
                                        # Clean up
                                        bpy.data.images.remove(temp_image)
                                        
                                        # Restore original settings
                                        scene.render.image_settings.file_format = original_format
                                        scene.render.image_settings.quality = original_quality
                                    else:
                                        # Simple copy without compression
                                        shutil.copy2(src_path, dst_path)
                        except self.DIFETTI_DI_PROGRAMMAZIONE:
                            raise          # T4
                        except Exception as e:
                            self._fallito(f"texture for {obj.name}", str(e), e)

