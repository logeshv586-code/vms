import React from "react";

export const DivWrapper = () => {
  return (
    <div className="absolute w-[280px] h-[340px] top-[100px] left-[370px] bg-white border border-gray-200 rounded-md">
      {/* Middle panel */}
      <div className="p-4">
        <h3 className="text-black font-medium mb-3">Live Feeds</h3>
        <div className="grid grid-cols-2 gap-2">
          <div className="aspect-video bg-gray-100 border border-gray-200 rounded flex items-center justify-center">
            <span className="text-gray-500 text-xs">Camera 1</span>
          </div>
          <div className="aspect-video bg-gray-100 border border-gray-200 rounded flex items-center justify-center">
            <span className="text-gray-500 text-xs">Camera 2</span>
          </div>
          <div className="aspect-video bg-gray-100 border border-gray-200 rounded flex items-center justify-center">
            <span className="text-gray-500 text-xs">Camera 3</span>
          </div>
          <div className="aspect-video bg-gray-100 border border-gray-200 rounded flex items-center justify-center">
            <span className="text-gray-500 text-xs">Camera 4</span>
          </div>
        </div>
      </div>
    </div>
  );
};
