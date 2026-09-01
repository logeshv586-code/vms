import React from "react";

export const ContainerWrapper = () => {
  return (
    <div className="absolute w-[300px] h-[200px] top-[100px] left-[50px] bg-white border border-gray-200 rounded-md">
      {/* Left panel container */}
      <div className="p-4">
        <h3 className="text-black font-medium mb-3">Camera Controls</h3>
        <div className="space-y-2">
          <button className="w-full px-3 py-2 text-left text-black hover:bg-gray-100 rounded transition-colors">
            Camera 1
          </button>
          <button className="w-full px-3 py-2 text-left text-black hover:bg-gray-100 rounded transition-colors">
            Camera 2
          </button>
          <button className="w-full px-3 py-2 text-left text-black hover:bg-gray-100 rounded transition-colors">
            Camera 3
          </button>
        </div>
      </div>
    </div>
  );
};
